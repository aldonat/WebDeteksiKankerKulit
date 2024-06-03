from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import check_password_hash, generate_password_hash
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
import os
from datetime import datetime

app = Flask(__name__)
# Koneksi
app.secret_key = 'kanker'
app.config['MYSQL_HOST'] = 'sql12.freemysqlhosting.net'
app.config['MYSQL_USER'] = 'sql12711051'
app.config['MYSQL_PASSWORD'] = 'VRln8NnhSR'
app.config['MYSQL_DB'] = 'sql12711051'
app.config['MYSQL_PORT'] = 3306

mysql = MySQL(app)

@app.route('/')
def index():
    if 'loggedin' in session:
        return render_template('index.html', loggedin=True, username=session['username'])
    return render_template('index.html', loggedin=False)

# Registrasi
@app.route('/registrasi', methods=('GET', 'POST'))
def registrasi():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Cek Username atau email
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM user WHERE username=%s OR email=%s', (username, email,))
        akun = cursor.fetchone()
        if akun is None:
            cursor.execute('INSERT INTO user (username, email, password) VALUES (%s, %s, %s)',
                           (username, email, generate_password_hash(password)))
            mysql.connection.commit()
            flash('Registrasi Berhasil', 'success')
        else:
            flash('Username atau email sudah ada', 'danger')
    return render_template('registrasi.html')

# Login
@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        # Cek data username
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM user WHERE email=%s', (email,))
        akun = cursor.fetchone()

        if akun is None:
            flash('Login Gagal, Cek Email Anda', 'danger')
        elif not check_password_hash(akun[3], password):
            flash('Login gagal, Cek Password Anda', 'danger')
        else:
            session['loggedin'] = True
            session['id'] = akun[0]
            session['username'] = akun[1]
            return redirect(url_for('classify_image'))
        
    return render_template('login.html')

# Log out
@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('username', None)
    session.pop('id', None)
    return redirect(url_for('index'))  # Redirect to the index route

# Load the model
model = load_model('kanker2.h5')
class_labels = ['Actinic Keratosis', 'Basal Cell Carcinoma', 'Benign Keratosis', 'Dermatofibroma', 'Melanoma', 'Nevus', 'Vascular Lesions']

# Function to preprocess the image
def preprocess_image(img_path):
    img = image.load_img(img_path, target_size=(64, 64))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array /= 255.0
    return img_array

@app.route('/app', methods=['GET', 'POST'], endpoint='classify_image')
def classify_image():
    if 'loggedin' not in session:
        flash('Please log in to access this feature.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', message='No file part', loggedin=True)

        file = request.files['file']

        if file.filename == '':
            return render_template('index.html', message='No selected file', loggedin=True)

        if file:
            file_path = os.path.join('static', file.filename)
            file.save(file_path)
            processed_img = preprocess_image(file_path)
            predictions = model.predict(processed_img)[0]
            predicted_class_index = np.argmax(predictions)
            predicted_class = class_labels[predicted_class_index]
            probability = float(predictions[predicted_class_index])

            # Simpan data prediksi ke dalam tabel history
            cursor = mysql.connection.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO history (user_id, image_path, timestamp, label, probability) VALUES (%s, %s, %s, %s, %s)',
                           (session['id'], file_path, timestamp, predicted_class, probability))
            mysql.connection.commit()

            return render_template(
                'index.html',
                message='Predicted class: {}'.format(predicted_class),
                predictions=predictions,
                class_labels=class_labels,
                image_file=file_path,
                loggedin=True
            )

    return render_template('index.html', loggedin=True)

@app.route('/history')
def history():
    if 'loggedin' not in session:
        flash('Please log in to access this feature.', 'danger')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT image_path, timestamp, label, probability FROM history WHERE user_id = %s', (session['id'],))
    history_data = cursor.fetchall()  # Mengambil semua hasil dari query

    # Debug print untuk melihat isi dari history_data
    print("History Data:", history_data)  # Tambahkan ini untuk debug, memastikan data tidak kosong

    return render_template('history.html', history_data=history_data)

if __name__ == '__main__':
    app.run(debug=True,port='2828', host='0.0.0.0')
