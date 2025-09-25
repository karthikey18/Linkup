from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
import sqlite3, os, uuid, random
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Folder setup
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['AVATAR_FOLDER'] = 'static/avatars'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)

# Mail setup
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ckarthikeya.chillarigil@gmail.com'
app.config['MAIL_PASSWORD'] = 'rgsg amvb slbc vejn'
mail = Mail(app)

# OTP storage
otp_store = {}

# Database setup
def init_db():
    if not os.path.exists('users.db'):
        print("🛠 Creating new users.db")
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        avatar TEXT,
        bio TEXT,
        verified INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    print("✅ users table created or verified")

init_db()

posts = []

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = generate_password_hash(request.form['password'])
        email = request.form.get('email')
        phone = request.form.get('phone')
        avatar = request.files.get('avatar')
        avatar_filename = None

        if avatar and avatar.filename != '':
            avatar_filename = secure_filename(f"{uuid.uuid4()}_{avatar.filename}")
            avatar.save(os.path.join(app.config['AVATAR_FOLDER'], avatar_filename))

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email))
        existing_user = c.fetchone()
        conn.close()
        if existing_user:
            flash("Username or email already exists", "error")
            return redirect(url_for('signup'))

        otp = str(random.randint(100000, 999999))
        otp_store[email] = {
            'username': username,
            'password': password,
            'phone': phone,
            'avatar': avatar_filename,
            'otp': otp
        }

        msg = Message('Your LinkUp OTP', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your OTP is: {otp}'
        mail.send(msg)

        flash("OTP sent to your email", "success")
        return redirect(url_for('verify_otp', email=email))

    return render_template('signup.html')

@app.route('/verify-otp/<email>', methods=['GET', 'POST'])
def verify_otp(email):
    if request.method == 'POST':
        entered_otp = request.form['otp']
        data = otp_store.get(email)
        if data and data['otp'] == entered_otp:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("INSERT INTO users (username, password, email, phone, avatar, verified) VALUES (?, ?, ?, ?, ?, ?)",
                      (data['username'], data['password'], email, data['phone'], data['avatar'], 1))
            conn.commit()
            conn.close()
            otp_store.pop(email)
            flash("Account created successfully!", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP", "error")
    return render_template('verify_otp.html', email=email)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[0], password):
            session['username'] = username
            return redirect(url_for('feed', username=username))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip()
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()
        if not user:
            flash("Email not found", "error")
            return redirect(url_for('forgot_password'))

        otp = str(random.randint(100000, 999999))
        otp_store[email] = {'otp': otp}
        msg = Message('LinkUp Password Reset OTP', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = f'Your OTP to reset your password is: {otp}'
        mail.send(msg)
        flash("OTP sent to your email", "success")
        return redirect(url_for('reset_password', email=email))
    return render_template('forgot_password.html')

@app.route('/reset-password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    if request.method == 'POST':
        entered_otp = request.form['otp']
        new_password = generate_password_hash(request.form['new_password'])
        data = otp_store.get(email)
        if data and data['otp'] == entered_otp:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("UPDATE users SET password = ? WHERE email = ?", (new_password, email))
            conn.commit()
            conn.close()
            otp_store.pop(email)
            flash("Password reset successful", "success")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP", "error")
    return render_template('reset_password.html', email=email)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/feed/<username>', methods=['GET', 'POST'])
def feed(username):
    if 'username' not in session or session['username'] != username:
        return redirect(url_for('login'))
    if request.method == 'POST':
        content = request.form['post'].strip()
        image = request.files.get('image')
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        post_id = str(uuid.uuid4())
        image_filename = None
        if image and image.filename != '':
            image_filename = secure_filename(f"{post_id}_{image.filename}")
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
        if not any(p['username'] == username and p['content'] == content for p in posts):
            posts.append({
                'id': post_id,
                'username': username,
                'content': content,
                'timestamp': timestamp,
                'image': image_filename,
                'likes': 0,
                'comments': []
            })
        return redirect(url_for('feed', username=username))
    return render_template('feed.html', username=username, posts=posts)

@app.route('/like/<post_id>')
def like(post_id):
    for post in posts:
        if post['id'] == post_id:
            post['likes'] += 1
            break
    return redirect(request.referrer)

@app.route('/comment/<post_id>', methods=['POST'])
def comment(post_id):
    comment_text = request.form['comment'].strip()
    for post in posts:
        if post['id'] == post_id:
            post['comments'].append(comment_text)
            break
    return redirect(request.referrer)

@app.route('/profile/<username>')
def profile(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT email, phone, avatar, bio FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    user_posts = [p for p in posts if p['username'] == username]
    return render_template('profile.html', username=username, email=user[0], phone=user[1], avatar=user[2], bio=user[3], posts=user_posts)

@app.route('/about/<username>')
def about(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT avatar, bio FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    conn.close()
    return render_template('about.html', username=username, avatar=user[0], bio=user[1])

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)



