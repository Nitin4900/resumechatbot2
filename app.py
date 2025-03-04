from flask import Flask, request, render_template_string, flash, redirect, url_for
import pdfplumber
import docx
import re
import string
import spacy
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = 'super secret key'
nlp = spacy.load("en_core_web_lg")

# HTML template for the web form
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Resume & Job Description Checker</title>
</head>
<body>
    <h2>Upload Resume and Job Description</h2>
    <form method="post" action="/" enctype="multipart/form-data">
        <label>Resume:</label>
        <input type="file" name="resume"><br><br>
        <label>Job Description:</label>
        <input type="file" name="job_description"><br><br>
        <input type="submit" value="Upload">
    </form>

    {% if score %}
        <h3>Match Score: {{ score }}%</h3>
        <h3>Category: {{ category }}</h3>
        <h3>Extracted Emails: {{ emails }}</h3>
        <h4>Cleaned Resume:</h4>
        <pre>{{ cleaned_resume }}</pre>
        <h4>Cleaned Job Description:</h4>
        <pre>{{ cleaned_jd }}</pre>
    {% endif %}

    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul>
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
</body>
</html>
'''


@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        resume_file = request.files['resume']
        jd_file = request.files['job_description']

        if resume_file and jd_file:
            resume_path = secure_filename(resume_file.filename)
            jd_path = secure_filename(jd_file.filename)
            resume_file.save(resume_path)
            jd_file.save(jd_path)

            # Process the files
            score, category, emails, cleaned_resume, cleaned_jd = process_files(resume_path, jd_path)

            # Clean up uploaded files
            os.remove(resume_path)
            os.remove(jd_path)

            if score is None:
                flash('Failed to process files.')
                return redirect(url_for('upload_file'))

            return render_template_string(HTML_TEMPLATE, score=f"{score:.2f}", category=category,
                                          emails=", ".join(emails), cleaned_resume=cleaned_resume,
                                          cleaned_jd=cleaned_jd)

    return render_template_string(HTML_TEMPLATE, score=None)


def process_files(resume_path, jd_path):
    resume_text = extract_text(resume_path)
    jd_text = extract_text(jd_path)

    if 'Error' in resume_text or 'Error' in jd_text:
        return None, "Error extracting text", [], "", ""

    cleaned_resume = clean_text(resume_text)
    cleaned_jd = clean_text(jd_text)

    emails = extract_emails(resume_text)

    resume_tokens = process_text(cleaned_resume)
    jd_tokens = process_text(cleaned_jd)

    match_percentage = calculate_similarity(resume_tokens, jd_tokens)
    category = classify_similarity(match_percentage)

    return match_percentage, category, emails, cleaned_resume, cleaned_jd


def extract_text(file_path):
    """Extract text from PDF, TXT, or DOCX files."""
    file_extension = file_path.lower().split('.')[-1]
    try:
        if file_extension == 'pdf':
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
        elif file_extension == 'txt':
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
        elif file_extension == 'docx':
            doc = docx.Document(file_path)
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        else:
            raise ValueError(f"Unsupported file format: .{file_extension}")
        return text
    except PermissionError:
        return "Error: Permission denied."
    except Exception as e:
        return f"Error: {str(e)}"


def extract_emails(text):
    """Extracts email addresses using regex."""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.findall(email_pattern, text)


def clean_text(text):
    """Cleans extracted text."""
    doc = nlp(text)
    cleaned_tokens = [token.lemma_ for token in doc if not token.is_stop and not token.is_punct and not token.is_space]
    cleaned_text = " ".join(cleaned_tokens)
    return cleaned_text


def process_text(text):
    """Tokenize text and remove stopwords."""
    doc = nlp(text)
    return [token.text for token in doc if not token.is_stop]


def calculate_similarity(resume_tokens, jd_tokens):
    """Calculate similarity using spaCy word vectors."""
    resume_doc = nlp(" ".join(resume_tokens))
    jd_doc = nlp(" ".join(jd_tokens))
    similarity = resume_doc.similarity(jd_doc) if resume_doc and jd_doc else 0
    return similarity * 100


def classify_similarity(score):
    """Classify similarity score."""
    if score < 20:
        return "Bad"
    elif score < 50:
        return "Good"
    elif score < 70:
        return "Better"
    elif score < 95:
        return "Best"
    else:
        return "Doubtful"


if __name__ == '__main__':
    app.run(debug=True)
