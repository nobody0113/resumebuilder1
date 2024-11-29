import os
from flask import Flask, render_template, request, redirect, send_file, session, url_for, flash
import sqlite3
import pdfkit
from werkzeug.security import generate_password_hash, check_password_hash
from database import init_db

from flask_wtf import CSRFProtect


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a random secret key

# Initialize CSRF protection


UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize the database
init_db()

# Ensure the PDF directory exists
if not os.path.exists('static/pdfs'):
    os.makedirs('static/pdfs')

@app.route('/')
def index():
    if 'logged_in' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    return render_template('index.html')  # Render the index page when logged in

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('resumes.db')
        cursor = conn.cursor()
        try:
            hashed_password = generate_password_hash(password)  # Hash the password
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
            conn.commit()
            flash('Registration successful! You can now log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose another one.')
        finally:
            conn.close()
    
    return render_template('register.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('resumes.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):  # Check the hashed password
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful!')
            return redirect(url_for('index'))  # Redirect to the index page after successful login
        else:
            flash('Invalid username or password. Please try again.')
    
    return render_template('login.html')


# Logout Route
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

# The rest of your code remains unchanged...



@app.route('/create_resume', methods=['GET', 'POST'])
def create_resume():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        address = request.form['address']
        education = request.form['education']
        experience = request.form['experience']
        skills = request.form['skills']
        template = request.form['template']
        about = request.form['about']
        
        # Get user_id from session
        username = session['username']
        conn = sqlite3.connect('resumes.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_id = cursor.fetchone()[0]
        
        # Insert resume linked to user_id
        cursor.execute('''
            INSERT INTO resumes (user_id, name, email, phone, address, education, experience, skills, template, about)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, email, phone, address, education, experience, skills, template, about))
        conn.commit()
        conn.close()
        flash('Resume created successfully!')
        return redirect(url_for('view_resumes'))
    
    return render_template('create_resume.html')



@app.route('/view_resumes')
def view_resumes():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    user_id = cursor.fetchone()['id']

    # Retrieve only resumes for the current user
    cursor.execute('SELECT * FROM resumes WHERE user_id = ?', (user_id,))
    resumes = cursor.fetchall()  # Now returns dictionary-like rows
    conn.close()
    return render_template('view_resumes.html', resumes=resumes)


@app.route('/resume/<int:resume_id>')
def resume(resume_id):
    conn = sqlite3.connect('resumes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM resumes WHERE id=?', (resume_id,))
    resume = cursor.fetchone()
    conn.close()

    # Use template from database or default if not found
    template_name = resume[9] if resume[9] in os.listdir('templates') else 'template1.html'
    return render_template(template_name, resume=resume)


# Set the correct path to wkhtmltopdf on your system
WKHTMLTOPDF_PATH = r"/bin/wkhtmltopdf"  # Use raw string or double backslashes
PDFKIT_CONFIG = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

@app.route('/download_resume/<int:resume_id>')
def download_resume(resume_id):
    # Fetch resume data from the database
    conn = sqlite3.connect('resumes.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM resumes WHERE id = ?', (resume_id,))
    resume = cursor.fetchone()
    conn.close()

    if resume is None:
        flash('Resume not found!')
        return redirect(url_for('view_resumes'))

    # Get the template name from the resume data
    template_name = resume[9]  # Assuming the template field is at index 8

    # Render the resume as HTML for PDF conversion
    rendered_html = render_template(template_name, resume=resume)

    # Define PDF file path
    pdf_filename = f"resume_{resume_id}.pdf"
    pdf_path = os.path.join('static', 'pdfs', pdf_filename)

    # PDF generation options
    options = {
        'page-size': 'A4',
        'margin-top': '0.75in',
        'margin-right': '0.75in',
        'margin-bottom': '0.75in',
        'margin-left': '0.75in',
        'quiet': True,  # Set to True to suppress output
    }

    # Convert HTML to PDF
    try:
        pdfkit.from_string(rendered_html, pdf_path, configuration=PDFKIT_CONFIG, options=options)
    except Exception as e:
        flash(f'Error generating PDF: {e}')
        return redirect(url_for('view_resumes'))

    # Send the PDF as a downloadable file
    return send_file(pdf_path, as_attachment=True)



def get_db_connection():
    conn = sqlite3.connect('resumes.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/delete_resume/<int:resume_id>', methods=['POST'])
def delete_resume(resume_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    # Get the user_id from the session
    username = session['username']
    conn = sqlite3.connect('resumes.db')
    cursor = conn.cursor()
    
    # Get user_id based on the logged-in username
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    user_id = cursor.fetchone()
    
    if user_id is None:
        flash('User not found.')
        return redirect(url_for('view_resumes'))
    
    user_id = user_id[0]
    
    # Check if the resume belongs to the logged-in user
    cursor.execute('SELECT * FROM resumes WHERE id = ? AND user_id = ?', (resume_id, user_id))
    resume = cursor.fetchone()
    
    if resume is None:
        flash('Resume not found or you do not have permission to delete it.')
        return redirect(url_for('view_resumes'))

    # Proceed with deleting the resume from the database
    cursor.execute('DELETE FROM resumes WHERE id = ?', (resume_id,))
    conn.commit()
    conn.close()

    flash('Resume deleted successfully!')
    return redirect(url_for('view_resumes'))











@app.route('/view/<template_name>')
def view_template(template_name):
    allowed_templates = ['creative', 'modern', 'classic','elegant','sleek','mini']  # List of allowed templates

    # Check if the template is allowed and exists
    if template_name in allowed_templates:
        return render_template(f'{template_name}.html')
    else:
        return "Template not found", 404





if __name__ == '__main__':
    app.run(debug=True)
