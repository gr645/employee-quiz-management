from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import csv
import pandas as pd
from datetime import datetime
import io
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Required for session management

# MongoDB connection
MONGO_URI = "mongodb://localhost:27017/quiz"
client = MongoClient(MONGO_URI)
db = client['quiz']

# Admin credentials (for simplicity, hardcoded here)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

# Routes
@app.route('/')
def home():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('create_quiz'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        # Check admin login first
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            print("Admin login successful")
            session['is_admin'] = True
            session['user_id'] = 'admin'
            return redirect(url_for('create_quiz'))
        
        # Regular user login
        user = db.users.find_one({'username': username})
        if user and user['password'] == password:
            session['user_id'] = str(user['_id'])
            session['is_admin'] = False
            
            # Debug prints
            print(f"User logged in - Department: {user['department']}")
            quiz_count = db.quizzes.count_documents({'department': user['department']})
            print(f"Found {quiz_count} quizzes for department: {user['department']}")
            
            if quiz_count > 0:
                return redirect(url_for('quiz'))
            else:
                flash("No quizzes are available for your department at this time.", "info")
                return redirect(url_for('user_dashboard'))
        
        error = "Invalid username or password"
        print(f"Login failed for username: {username}")
    
    return render_template('login.html', error=error)

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    department = request.form.get('department', '').strip()
    
    if not username or not email or not password or not department:
        flash("All fields are required", "error")
        return redirect(url_for('login'))
    
    # Check if username exists
    existing_username = db.users.find_one({'username': username})
    if existing_username:
        flash("This username is already taken", "error")
        return redirect(url_for('login'))
    
    # Check if email exists
    existing_email = db.users.find_one({'email': email})
    if existing_email:
        flash("This email is already registered", "error")
        return redirect(url_for('login'))
    
    # If both checks pass, create new user
    user = {
        'username': username,
        'email': email,
        'password': password,  # In production, this should be hashed
        'department': department,
        'created_at': datetime.now()
    }
    
    db.users.insert_one(user)
    flash("Signup successful! You can now log in.", "success")
    return redirect(url_for('login'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/create-quiz')
def create_quiz():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    # Get all scores
    scores = list(db.scores.find().sort('submission_date', -1))
    
    # Calculate analytics
    total_submissions = len(scores)
    avg_score = sum(s['score'] for s in scores) / total_submissions if total_submissions > 0 else 0
    
    # Get department-wise statistics
    dept_stats = {}
    for score in scores:
        dept = score['department']
        if dept not in dept_stats:
            dept_stats[dept] = {'count': 0, 'total': 0}
        dept_stats[dept]['count'] += 1
        dept_stats[dept]['total'] += score['score']
    
    for dept in dept_stats:
        dept_stats[dept]['avg'] = dept_stats[dept]['total'] / dept_stats[dept]['count']
    
    return render_template('create_quiz.html', 
                         scores=scores,
                         total_submissions=total_submissions,
                         avg_score=avg_score,
                         dept_stats=dept_stats)

# Update the save_quiz route to include scheduling
@app.route('/save-quiz', methods=['POST'])
def save_quiz():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    
    file = request.files['quiz_file']
    department = request.form['department']
    timer = int(request.form.get('timer', 60))  # Question timer
    
    # Get scheduling information
    start_time = request.form.get('start_time')  # Format: "YYYY-MM-DD HH:MM"
    duration_hours = int(request.form.get('duration_hours', 0))
    duration_minutes = int(request.form.get('duration_minutes', 0))
    
    if not file or not department or not start_time:
        flash("File, department and start time are required", "error")
        return redirect(url_for('create_quiz'))
    
    try:
        # Convert start_time string to datetime object
        start_datetime = datetime.strptime(start_time, "%Y-%m-%dT%H:%M")
        
        # Calculate end time
        duration_in_minutes = (duration_hours * 60) + duration_minutes
        end_datetime = start_datetime + pd.Timedelta(minutes=duration_in_minutes)
        
        # Read Excel file
        df = pd.read_excel(file)
        
        # Validate Excel structure
        required_columns = ['question', 'option1', 'option2', 'option3', 'option4', 'answer']
        if not all(col in df.columns for col in required_columns):
            missing_cols = [col for col in required_columns if col not in df.columns]
            flash(f"Excel file must contain columns: {', '.join(required_columns)}", "error")
            return redirect(url_for('create_quiz'))
        
        # Format questions for database
        formatted_quizzes = []
        for _, row in df.iterrows():
            quiz = {
                'department': department,
                'question': row['question'],
                'options': [
                    row['option1'],
                    row['option2'],
                    row['option3'],
                    row['option4']
                ],
                'answer': row['answer'],
                'timer': timer,
                'start_time': start_datetime,
                'end_time': end_datetime,
                'duration_minutes': duration_in_minutes,
                'created_at': datetime.now()
            }
            formatted_quizzes.append(quiz)
        
        # Save quizzes to database
        if formatted_quizzes:
            result = db.quizzes.insert_many(formatted_quizzes)
            print(f"Successfully inserted {len(result.inserted_ids)} questions")
            print(f"First question department: {formatted_quizzes[0]['department']}")
            flash(f"Quiz uploaded successfully! Added {len(formatted_quizzes)} questions.", "success")
        else:
            flash("No valid questions found in the file", "error")
            
    except Exception as e:
        print(f"Error saving quiz: {str(e)}")
        flash(f"An error occurred while processing the file: {str(e)}", "error")
        return redirect(url_for('create_quiz'))
    
    return redirect(url_for('create_quiz'))

@app.route('/user-dashboard')
def user_dashboard():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = db.users.find_one({'_id': ObjectId(user_id)})
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
    
    # Get user's quiz submission if it exists
    submission = db.scores.find_one({'user_id': user_id})
    
    # Get current time
    current_time = datetime.now()
    
    # Check if there's an available and active quiz for the user's department
    available_quiz = db.quizzes.find_one({
        'department': user['department'],
        'start_time': {'$lte': current_time},
        'end_time': {'$gte': current_time}
    })
    
    # Check if there's an expired quiz
    expired_quiz = db.quizzes.find_one({
        'department': user['department'],
        'end_time': {'$lt': current_time}
    })
    
    quiz_status = 'none'  # Default status
    if available_quiz:
        quiz_status = 'available'
    elif expired_quiz:
        quiz_status = 'expired'
    
    return render_template('dashboard.html', 
                         user=user, 
                         submission=submission, 
                         quiz_status=quiz_status)

@app.route('/quiz')
def quiz():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = db.users.find_one({'_id': ObjectId(user_id)})
    
    # Check if user has already taken a quiz
    existing_submission = db.scores.find_one({'user_id': user_id})
    if existing_submission:
        flash("You have already completed the quiz.", "info")
        return redirect(url_for('user_dashboard'))
    
    # Get current time
    current_time = datetime.now()
    
    # Find available quizzes for the department that are currently active
    quizzes = list(db.quizzes.find({
        'department': user['department'],
        'start_time': {'$lte': current_time},
        'end_time': {'$gte': current_time}
    }))
    
    if not quizzes:
        flash("No quizzes are currently available for your department.", "info")
        return redirect(url_for('user_dashboard'))
    
    # Check if quiz has been started
    quiz_started = session.get('quiz_started', False)
    
    if not quiz_started:
        # Return initial quiz page with empty quiz object
        return render_template('save-quiz.html', 
                            user=user,
                            quiz_started=False,
                            has_taken_quiz=False,
                            quiz={},  # Add empty quiz object
                            quizzes=quizzes)  # Add quizzes list
    
    # Get current question
    question_index = int(request.args.get('question', 0))
    if question_index >= len(quizzes):
        return redirect(url_for('quiz_complete'))
    
    current_quiz = quizzes[question_index]
    session['current_question'] = question_index
    
    return render_template('save-quiz.html', 
                         user=user,
                         quiz=current_quiz,
                         quiz_started=True,
                         has_taken_quiz=False,
                         quizzes=quizzes,
                         current_question=question_index,
                         total_questions=len(quizzes),
                         question_number=question_index + 1,
                         timer=current_quiz.get('timer', 60))  # Get timer with default 60
@app.route('/start-quiz', methods=['POST'])
def start_quiz():
    if not session.get('user_id') or session.get('is_admin'):
        return redirect(url_for('login'))
    
    # Initialize quiz session
    session['quiz_started'] = True
    session['user_answers'] = {}
    
    return redirect(url_for('quiz', question=0))

@app.route('/submit-answer', methods=['POST'])
def submit_answer():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    question_id = request.form.get('question_id')
    answer = request.form.get('answer', '')  # Default to empty string if no answer
    action = request.form.get('action')
    time_expired = request.form.get('time_expired', 'false')

    # Get current question index from session
    current_question = session.get('current_question', 0)
    
    # Save the answer (even if empty due to timeout)
    if 'answers' not in session:
        session['answers'] = {}
    
    # Only save non-empty answers
    if answer:
        session['answers'][question_id] = answer

    # Get all quizzes for the user's department
    user = db.users.find_one({'_id': ObjectId(session['user_id'])})
    quizzes = list(db.quizzes.find({'department': user['department']}))
    
    # Handle time expired, next action, or finish
    if time_expired == 'true' or action == 'next':
        if current_question < len(quizzes) - 1:
            session['current_question'] = current_question + 1
            return redirect(url_for('quiz', question=current_question + 1))
        else:
            return calculate_and_save_score()
    elif action == 'finish':
        return calculate_and_save_score()
    
    # If we get here, something went wrong
    flash('An error occurred. Please try again.', 'error')
    return redirect(url_for('quiz'))

def calculate_and_save_score():
    user_id = session['user_id']
    user = db.users.find_one({'_id': ObjectId(user_id)})
    
    # Get all quizzes for the user's department
    quizzes = list(db.quizzes.find({'department': user['department']}))
    
    # Calculate score
    score = 0
    total_questions = len(quizzes)
    questions_data = []
    
    for quiz in quizzes:
        quiz_id = str(quiz['_id'])
        user_answer = session.get('answers', {}).get(quiz_id, '')
        correct_answer = str(quiz['answer'])  # Convert answer to string
        
        # Compare answers, handling empty responses
        is_correct = False
        if user_answer:  # Only check if user provided an answer
            is_correct = user_answer.lower() == correct_answer.lower()
        
        if is_correct:
            score += 1
        
        questions_data.append({
            'question': quiz['question'],
            'options': quiz['options'],
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct
        })
    
    score_percentage = (score / total_questions) * 100
    submission_time = datetime.now()
    
    # Store questions data temporarily in session
    session['quiz_results'] = {
        'score': score_percentage,
        'total_questions': total_questions,
        'correct_answers': score,
        'questions': questions_data
    }
    
    # Save score to database
    score_data = {
        'user_id': str(user_id),
        'username': user['username'],
        'department': user['department'],
        'score': score_percentage,
        'submission_date': submission_time.strftime('%Y-%m-%d'),
        'submission_time': submission_time.strftime('%H:%M:%S'),
        'total_questions': total_questions,
        'correct_answers': score,
        'created_at': submission_time
    }
    
    try:
        db.scores.insert_one(score_data)
        # Clear quiz session data
        session.pop('quiz_started', None)
        session.pop('answers', None)
        session.pop('current_question', None)
        
        return render_template('quiz_result.html', 
                            score=score_percentage,
                            total_questions=total_questions,
                            correct_answers=score)
    except Exception as e:
        print("Error saving score:", str(e))
        flash("Error saving your quiz results", "error")
        return redirect(url_for('user_dashboard'))

@app.route('/view-answers')
def view_answers():
    quiz_results = session.get('quiz_results')
    if not quiz_results:
        return redirect(url_for('user_dashboard'))
    
    # Clear results from session after viewing
    session.pop('quiz_results', None)
    
    return render_template('view_answers.html',
                         score=quiz_results['score'],
                         total_questions=quiz_results['total_questions'],
                         correct_answers=quiz_results['correct_answers'],
                         questions=quiz_results['questions'])

# Add this temporary route to check quizzes
@app.route('/check-quizzes')
def check_quizzes():
    all_quizzes = list(db.quizzes.find())
    departments = db.quizzes.distinct('department')
    return {
        'quiz_count': len(all_quizzes),
        'departments': departments,
        'quizzes': [{
            'department': q['department'],
            'question': q['question']
        } for q in all_quizzes]
    }

@app.route('/debug-database')
def debug_database():
    # Check all users
    users = list(db.users.find({}, {'username': 1, 'department': 1}))
    
    # Check all quizzes
    quizzes = list(db.quizzes.find())
    
    return {
        'users': [{'username': u['username'], 'department': u['department']} for u in users],
        'quizzes': [{
            'department': q['department'],
            'question': q['question']
        } for q in quizzes],
        'quiz_count_by_dept': {
            dept: db.quizzes.count_documents({'department': dept})
            for dept in db.quizzes.distinct('department')
        }
    }

@app.route('/check-scores')
def check_scores():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
        
    scores = list(db.scores.find())
    return {
        'total_scores': len(scores),
        'scores': [{
            'username': s['username'],
            'department': s['department'],
            'score': s['score'],
            'submission_date': s['submission_date'],
            'submission_time': s['submission_time'],
            'total_questions': s['total_questions'],
            'correct_answers': s['correct_answers']
        } for s in scores]
    }

if __name__ == '__main__':
    app.run(debug=True)
