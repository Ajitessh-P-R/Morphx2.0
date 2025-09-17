import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///morphx.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@amrita.edu")

    # Supabase connection (defaults provided; override with environment variables in production)
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://bezxdiwknanntwnjkvuf.supabase.co")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJlenhkaXdrbmFubnR3bmprdnVmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTgwODA4NjYsImV4cCI6MjA3MzY1Njg2Nn0.4gV8lhZXP8tmn7fi-t4fr2_L6nD5I5ncd1Ww_YZeTkw")

