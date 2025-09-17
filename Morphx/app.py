import os
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config
from supabase import create_client, Client

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Supabase client (optional usage alongside local DB)
supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(48), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    blocked = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posts = db.relationship("Post", backref="author", lazy=True)
    comments = db.relationship("Comment", backref="author", lazy=True)
    likes = db.relationship("Like", backref="user", lazy=True)

    def get_id(self):
        return str(self.id)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(255), default="")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)

    comments = db.relationship("Comment", backref="post", lazy=True, cascade="all, delete-orphan")
    likes = db.relationship("Like", backref="post", lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "post_id", name="uq_user_post_like"),)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def save_image(file_storage):
    if not file_storage or file_storage.filename == "":
        return ""
    filename = secure_filename(file_storage.filename)
    if not allowed_image(filename):
        return ""
    name, ext = os.path.splitext(filename)
    safe_name = f"{name}_{int(datetime.utcnow().timestamp())}{ext}"
    path = UPLOAD_DIR / safe_name
    file_storage.save(path)
    return f"/static/uploads/{safe_name}"

@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))
    posts = (
        Post.query.filter_by(is_deleted=False)
        .order_by(Post.created_at.desc())
        .all()
    )
    return render_template("index.html", posts=posts)

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or Email already exists.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)
        user = User(username=username, email=email, password_hash=password_hash, is_admin=False)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        role = (request.form.get("role") or "user").strip()

        user = None
        if role == "admin":
            # Admin login must match predefined admin username
            if username != app.config["ADMIN_USERNAME"]:
                flash("Invalid admin credentials.", "error")
                return redirect(url_for("login"))
            user = User.query.filter_by(username=app.config["ADMIN_USERNAME"]).first()
            if not user:
                user = User(
                    username=app.config["ADMIN_USERNAME"],
                    email=app.config["ADMIN_EMAIL"],
                    password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
                    is_admin=True,
                )
                db.session.add(user)
                db.session.commit()
        else:
            user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if user.blocked and not user.is_admin:
                flash("Your account is blocked. Contact admin.", "error")
                return redirect(url_for("login"))
            login_user(user)
            flash("Login successful.", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password.", "error")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/profile")
@login_required
def profile():
    total_posts = Post.query.filter_by(user_id=current_user.id, is_deleted=False).count()
    total_comments = Comment.query.filter_by(user_id=current_user.id, is_deleted=False).count()
    total_likes = Like.query.filter_by(user_id=current_user.id).count()
    return render_template(
        "profile.html",
        total_posts=total_posts,
        total_comments=total_comments,
        total_likes=total_likes,
    )

@app.route("/profile/avatar", methods=["POST"])
@login_required
def upload_avatar():
    file = request.files.get("avatar")
    url = save_image(file)
    if not url:
        flash("Invalid image format.", "error")
        return redirect(url_for("profile"))
    current_user.avatar_url = url
    db.session.commit()
    flash("Avatar updated.", "success")
    return redirect(url_for("profile"))

@app.route("/create", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        image = request.files.get("image")
        if not content and not image:
            flash("Write something or add an image.", "error")
            return redirect(url_for("create_post"))
        image_url = save_image(image) if image else ""
        post = Post(content=content, image_url=image_url, user_id=current_user.id)
        db.session.add(post)
        db.session.commit()
        flash("Post created.", "success")
        return redirect(url_for("index"))
    return render_template("create_post.html")

@app.route("/like/<int:post_id>", methods=["POST"])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.is_deleted:
        return jsonify({"ok": False, "message": "Post removed"}), 400
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"ok": True, "liked": False, "count": len(post.likes)})
    like = Like(user_id=current_user.id, post_id=post_id)
    db.session.add(like)
    db.session.commit()
    return jsonify({"ok": True, "liked": True, "count": len(post.likes)})

@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def comment_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.is_deleted:
        flash("Post removed.", "error")
        return redirect(url_for("index"))
    content = (request.form.get("content") or "").strip()
    if not content:
        flash("Comment cannot be empty.", "error")
        return redirect(url_for("index"))
    c = Comment(content=content, user_id=current_user.id, post_id=post_id)
    db.session.add(c)
    db.session.commit()
    flash("Comment added.", "success")
    return redirect(url_for("index"))

def admin_only():
    return current_user.is_authenticated and current_user.is_admin

@app.route("/admin")
@login_required
def admin():
    if not admin_only():
        flash("Admin only.", "error")
        return redirect(url_for("index"))
    users = User.query.order_by(User.created_at.desc()).all()
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("admin.html", users=users, posts=posts)

@app.route("/admin/block/<int:user_id>", methods=["POST"])
@login_required
def admin_block_user(user_id):
    if not admin_only():
        return jsonify({"ok": False}), 403
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        return jsonify({"ok": False, "message": "Cannot block admin"}), 400
    user.blocked = True
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/admin/unblock/<int:user_id>", methods=["POST"])
@login_required
def admin_unblock_user(user_id):
    if not admin_only():
        return jsonify({"ok": False}), 403
    user = User.query.get_or_404(user_id)
    user.blocked = False
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/admin/delete_post/<int:post_id>", methods=["POST"])
@login_required
def admin_delete_post(post_id):
    if not admin_only():
        return jsonify({"ok": False}), 403
    post = Post.query.get_or_404(post_id)
    post.is_deleted = True
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/admin/restore_post/<int:post_id>", methods=["POST"])
@login_required
def admin_restore_post(post_id):
    if not admin_only():
        return jsonify({"ok": False}), 403
    post = Post.query.get_or_404(post_id)
    post.is_deleted = False
    db.session.commit()
    return jsonify({"ok": True})

@app.route("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)

def init_db():
    db.create_all()
    admin_user = User.query.filter_by(username=app.config["ADMIN_USERNAME"]).first()
    if not admin_user:
        admin_user = User(
            username=app.config["ADMIN_USERNAME"],
            email=app.config["ADMIN_EMAIL"],
            password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
            is_admin=True,
        )
        db.session.add(admin_user)
        db.session.commit()

if __name__ == "__main__":
    with app.app_context():
        init_db()
    try:
        import webbrowser
        webbrowser.open_new("http://127.0.0.1:5000/login")
    except Exception:
        pass
    app.run(debug=True)
