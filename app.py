import enum
import os
import shutil
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import send_file, abort
from flask import redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FileField
from wtforms.validators import DataRequired, Length
from flask_wtf.file import FileAllowed
from sqlalchemy.dialects.postgresql import JSON
from enum import Enum, auto
from enum import Enum
from sqlalchemy import JSON, Enum as SQLAlchemyEnum
app = Flask(__name__)
app.config['SECRET_KEY'] = 'nyonks-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nyonks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')  # Store uploads in static/uploads
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max file size

# Create uploads folder if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    bio = db.Column(db.Text)
    profile_pic = db.Column(db.String(255))  # Column for profile picture

    # Relationships
    enrollments = relationship('Enrollment', back_populates='user', cascade='all, delete-orphan')
    courses = relationship('Course', back_populates='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def enrolled_courses(self):
        """Returns list of courses the user is enrolled in"""
        return [enrollment.course for enrollment in self.enrollments]

    @property
    def enrolled_course_ids(self):
        """Returns list of course IDs the user is enrolled in"""
        return [enrollment.course_id for enrollment in self.enrollments]

    def is_enrolled_in_course(self, course_id):
        """Checks if user is enrolled in a specific course"""
        return any(enrollment.course_id == course_id for enrollment in self.enrollments)

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    progress = db.Column(db.Float, default=0.0)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships with back_populates
    user = relationship('User', back_populates='enrollments')
    course = relationship('Course', back_populates='enrollments')

    # Unique constraint to prevent duplicate enrollments
    __table_args__ = (db.UniqueConstraint('user_id', 'course_id', name='_user_course_uc'),)
class CourseCategory(Enum):
    PROGRAMMING = 'Programming'
    DATA_SCIENCE = 'Data Science'
    WEB_DEVELOPMENT = 'Web Development'
    MACHINE_LEARNING = 'Machine Learning'
    DESIGN = 'Design'
    BUSINESS = 'Business'
    OTHER = 'Other'

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    instructor = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = relationship('User', back_populates='courses')

    # Updated to use image_url instead of thumbnail_path
    image_url = db.Column(db.String(255), nullable=True)

    # New fields
    introduction = db.Column(db.Text, nullable=True)  # Course blog/introduction
    blog_images = db.Column(JSON, nullable=True)   # List of blog image URLs
    blog_videos = db.Column(JSON, nullable=True)   # List of blog video URLs
    blog_links = db.Column(JSON, nullable=True)    # List of blog links as dictionaries
    category = db.Column(SQLAlchemyEnum(CourseCategory), nullable=False, default=CourseCategory.OTHER)  # New category field

    # Relationships
    materials = relationship('Material', back_populates='course', cascade='all, delete-orphan')
    course_questions = relationship('CourseQuestion', back_populates='course', cascade='all, delete-orphan')
    enrollments = relationship('Enrollment', back_populates='course', cascade='all, delete-orphan')

    @property
    def display_image(self):
        """
        Returns the image URL, with a default fallback if no image is set
        """
        return self.image_url or '/static/a.jpg'

    def to_dict(self):
        """
        Convert course to dictionary for serialization
        """
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'instructor': self.instructor,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'image_url': self.display_image,
            'introduction': self.introduction,
            'category': self.category.value if self.category else None,
            'uploader': self.user.username if self.user else None,
            'total_enrollments': len(self.enrollments)
        }

    def get_user_enrollment(self, user_id):
        """
        Get enrollment for a specific user
        """
        return next((enrollment for enrollment in self.enrollments if enrollment.user_id == user_id), None)
class Material(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # video, document, etc.
    file_path = db.Column(db.String(255), nullable=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Use back_populates
    course = relationship('Course', back_populates='materials')

class CourseQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(255), nullable=False)

    # Use back_populates
    course = relationship('Course', back_populates='course_questions')
    
    # Optional: Add relationship for answers if needed
    answers = relationship('Answer', back_populates='question')

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('course_question.id'), nullable=False)
    answer_text = db.Column(db.String(255), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)

    # Use back_populates
    question = relationship('CourseQuestion', back_populates='answers')

 
    
 

class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollment.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('course_question.id'), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)

    # Relationships
    enrollment = relationship('Enrollment', backref='user_answers')
    question = relationship('CourseQuestion', backref='user_answers')

 
# Route for creating a course with image upload
@app.route('/admin/course/create', methods=['GET', 'POST'])
@login_required
def create_course():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title')
            description = request.form.get('description')
            instructor = request.form.get('instructor')
            
            # Validate required fields
            if not title or not description or not instructor:
                flash('Please fill in all required fields', 'danger')
                return redirect(url_for('create_course'))

            # Convert category, handle potential errors
            try:
                category = CourseCategory(request.form.get('category'))
            except ValueError:
                flash('Invalid course category', 'danger')
                return redirect(url_for('create_course'))

            introduction = request.form.get('introduction')
            blog_links = request.form.getlist('blog_links[]')  # Expecting JSON strings

            # Handle image upload for course
            image_url = None
            if 'course_image' in request.files:
                file = request.files['course_image']
                if file and file.filename != '':
                    try:
                        filename = secure_filename(file.filename)
                        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # Ensure the folder exists
                        file.save(file_path)
                        image_url = f'/static/uploads/{unique_filename}'
                    except Exception as e:
                        flash(f'Error uploading course image: {str(e)}', 'danger')
                        return redirect(url_for('create_course'))

            # Handle blog media upload
            blog_images = []
            blog_videos = []
            try:
                if 'blog_images[]' in request.files:
                    for file in request.files.getlist('blog_images[]'):
                        if file and file.filename != '':
                            filename = secure_filename(file.filename)
                            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                            file.save(file_path)
                            blog_images.append(f'/static/uploads/{unique_filename}')

                if 'blog_videos[]' in request.files:
                    for file in request.files.getlist('blog_videos[]'):
                        if file and file.filename != '':
                            filename = secure_filename(file.filename)
                            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                            file.save(file_path)
                            blog_videos.append(f'/static/uploads/{unique_filename}')
            except Exception as e:
                flash(f'Error uploading blog media: {str(e)}', 'danger')
                return redirect(url_for('create_course'))

            # Parse blog links
            parsed_links = []
            try:
                parsed_links = [json.loads(link) for link in blog_links if link]
            except json.JSONDecodeError:
                flash('Invalid blog link format', 'danger')
                return redirect(url_for('create_course'))

            # Create new course with current user as uploader
            new_course = Course(
                title=title,
                description=description,
                instructor=instructor,
                image_url=image_url,
                category=category,
                introduction=introduction,
                blog_images=blog_images,
                blog_videos=blog_videos,
                blog_links=parsed_links,
                user_id=current_user.id  # Add the current user as the uploader
            )

            # Add and commit to database
            db.session.add(new_course)
            db.session.commit()

            flash('Course created successfully!', 'success')
            return redirect(url_for('view_courses'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating course: {str(e)}")
            flash(f'An unexpected error occurred: {str(e)}', 'danger')
            return redirect(url_for('create_course'))

    # GET request
    return render_template('create_course.html')

@app.route('/courses', methods=['GET'])
def courses():
    # Fetch courses logic
    courses = Course.query.all()
    return render_template('courses.html', courses=courses)

@app.route('/enroll/<int:course_id>', methods=['GET', 'POST'])
@login_required
def enroll_course(course_id):
    # Fetch the course or return 404 if not found
    course = Course.query.get_or_404(course_id)
    
    # Check if user is already enrolled
    existing_enrollment = Enrollment.query.filter_by(
        user_id=current_user.id, 
        course_id=course_id
    ).first()
    
    if existing_enrollment:
        flash('You are already enrolled in this course', 'info')
        return redirect(url_for('course_detail', course_id=course_id))
    
    try:
        # Create new enrollment
        new_enrollment = Enrollment(
            user_id=current_user.id,
            course_id=course_id,
            progress=0.0,
            enrolled_at=datetime.utcnow(),
            last_accessed=datetime.utcnow()
        )
        
        # Add and commit the new enrollment
        db.session.add(new_enrollment)
        db.session.commit()
        
        # Flash success message
        flash(f'Successfully enrolled in {course.title}', 'success')
        
        # Redirect to course detail page
        return redirect(url_for('course_detail', course_id=course_id))
    
    except Exception as e:
        # Rollback the session in case of error
        db.session.rollback()
        
        # Log the error
        app.logger.error(f"Enrollment error: {str(e)}")
        
        # Flash error message
        flash('An error occurred while enrolling', 'danger')
        
        # Redirect to courses page
        return redirect(url_for('courses'))

@app.route('/course/<int:course_id>', methods=['GET'])
def course_detail(course_id):
    # Fetch the specific course
    course = Course.query.get_or_404(course_id)
    
    # Check if user is enrolled
    is_enrolled = False
    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, 
            course_id=course_id
        ).first()
        is_enrolled = enrollment is not None
    
    return render_template('course_detail.html', course=course, is_enrolled=is_enrolled)
@app.route('/admin/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)

    try:
        # Delete course image
        if course.image_url and os.path.exists(course.image_url.lstrip('/')):
            os.remove(course.image_url.lstrip('/'))

        # Delete course materials and their files
        for material in course.materials:
            # Delete file if it exists
            if material.file_path and os.path.exists(material.file_path):
                os.remove(material.file_path)
            
            # Delete material record from database
            db.session.delete(material)

        # Delete course folder if it exists
        course_folder = os.path.join('static', 'courses', str(course.id))
        if os.path.exists(course_folder):
            shutil.rmtree(course_folder)

        # Delete course from database
        db.session.delete(course)
        db.session.commit()

        flash('Course and all associated materials deleted successfully!', 'success')
        return redirect(url_for('admin'))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting course: {e}")
        flash('An error occurred while deleting the course', 'danger')
        return redirect(url_for('admin'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    courses = Course.query.order_by(Course.created_at.desc()).limit(6).all()
    return render_template('index.html', courses=courses)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
            
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)

        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                # Create a unique filename based on the username
                filename = f"{username}.{file.filename.rsplit('.', 1)[1].lower()}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                user.profile_pic = filename  # Save the filename to the user model

        db.session.add(user)
        db.session.commit()
        
        flash(' Registration successful!', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()   
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
            
        flash('Invalid email or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
 
@app.route('/admin/course/<int:course_id>/add_question', methods=['GET', 'POST'])
@login_required
def add_course_question(course_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)

    if request.method == 'POST':
        question_text = request.form.get('question_text')
        answers = request.form.getlist('answers')  # Use getlist to get multiple answers
        correct_answer_index = request.form.get('correct_answer')

        # Validate inputs
        if not question_text or not answers or not correct_answer_index:
            flash('Please fill out all fields', 'danger')
            return render_template('add_question.html', course=course)

        # Create the question
        question = CourseQuestion(
            course_id=course.id, 
            question_text=question_text,
            correct_answer=answers[int(correct_answer_index)]
        )
        db.session.add(question)
        db.session.commit()  # Commit to get question ID

        # Add answers
        for index, answer_text in enumerate(answers):
            is_correct = (index == int(correct_answer_index))
            answer = Answer(
                question_id=question.id, 
                answer_text=answer_text.strip(), 
                is_correct=is_correct
            )
            db.session.add(answer)

        db.session.commit()

        flash('Question added successfully!', 'success')
        return redirect(url_for('course_detail', course_id=course_id))

    return render_template('add_question.html', course=course)

@app.route('/admin/course/<int:course_id>/questions', methods=['GET'])
@login_required
def view_course_questions(course_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)
    questions = CourseQuestion.query.filter_by(course_id=course_id).all()

    return render_template('view_questions.html', course=course, questions=questions)

@app.route('/admin/question/<int:question_id>/delete', methods=['POST'])
@login_required
def delete_question(question_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    question = CourseQuestion.query.get_or_404(question_id)
    course_id = question.course_id

    try:
        # Delete associated answers first
        Answer.query.filter_by(question_id=question_id).delete()

        # Delete associated user answers
        UserAnswer.query.filter_by(question_id=question_id).delete()
        
        # Then delete the question
        db.session.delete(question)
        db.session.commit()

        flash('Question deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()  # Rollback in case of error
        app.logger.error(f"Error deleting question: {str(e)}")
        flash('An error occurred while deleting the question. Please try again.', 'danger')

    return redirect(url_for('view_course_questions', course_id=course_id))
@app.route('/course/<int:course_id>/quiz', methods=['GET', 'POST'])
@login_required
def course_quiz(course_id):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()

    if not enrollment:
        flash('You must be enrolled in the course to take the quiz', 'danger')
        return redirect(url_for('course_detail', course_id=course_id))

    questions = CourseQuestion.query.filter_by(course_id=course_id).all()

    if request.method == 'POST':
        correct_count = 0
        total_questions = len(questions)
        user_answers = {}

        # Avoid division by zero
        if total_questions == 0:
            flash('No questions available for this quiz.', 'warning')
            return redirect(url_for('course_detail', course_id=course_id))

        for question in questions:
            user_answer = request.form.get(f'question_{question.id}')
            user_answers[question.id] = user_answer
            is_correct = Answer.query.filter_by(id=user_answer, question_id=question.id, is_correct=True).first() is not None

            if user_answer is not None:
                # Record user's answer
                user_answer_record = UserAnswer(
                    enrollment_id=enrollment.id,
                    question_id=question.id,
                    is_correct=is_correct
                )
                db.session.add(user_answer_record)

                # Only count correct answers towards progress
                if is_correct:
                    correct_count += 1

        # Calculate progress based only on correct answers
        if correct_count > 0:
            progress_increment = (correct_count / total_questions) * 100
            enrollment.progress = min(enrollment.progress + progress_increment, 100)  # Ensure progress does not exceed 100%
        db.session.commit()

        # Prepare feedback
        feedback = []
        for question in questions:
            user_answer = user_answers.get(question.id)
            correct_answer = Answer.query.filter_by(question_id=question.id, is_correct=True).first()
            feedback.append({
                'question': question.question_text,
                'user_answer': user_answer,
                'correct_answer': correct_answer.answer_text if correct_answer else None,
                'is_correct': user_answer == (correct_answer.id if correct_answer else None),
            })

        flash(f'Quiz completed! You scored {correct_count}/{total_questions}', 'success')
        return render_template('quiz_feedback.html', feedback=feedback, course=course, total_questions=total_questions)

    return render_template('course_quiz.html', course=course, questions=questions)  

@app.route('/dashboard')
@login_required
def dashboard():
    enrolled_courses = Course.query.join(Enrollment).filter(
        Enrollment.user_id == current_user.id
    ).all()
    
    # Calculate progress for each enrolled course
    for course in enrolled_courses:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, 
            course_id=course.id
        ).first()
        
        # Calculate progress based on quiz answers
        total_questions = CourseQuestion.query.filter_by(course_id=course.id).count()
        if total_questions > 0:
            correct_answers = UserAnswer.query.join(Enrollment).filter(
                Enrollment.user_id == current_user.id,
                Enrollment.course_id == course.id,
                UserAnswer.is_correct == True
            ).count()
            
            enrollment.progress = (correct_answers / total_questions) * 100
            db.session.commit()

    return render_template('dashboard.html', enrolled_courses=enrolled_courses)
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        bio = request.form['bio']
        current_user.bio = bio
        
        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                # Create a unique filename based on the username
                filename = f"{current_user.username}.{file.filename.rsplit('.', 1)[1].lower()}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                current_user.profile_pic = filename  # Save only the filename
                db.session.commit()
        
        db.session.commit()  # Commit the changes to the database
        flash('Your profile has been updated!', 'success')
        return redirect(url_for('profile'))
    
    return render_template('profile.html')
@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_query = request.form['search_query']
        return redirect(url_for('search_results', query=search_query))
    print("Rendering search template...")
    return render_template('search_results.html')
@app.route('/search/results/<query>')
def search_results(query):
    results = []  # Replace with your search logic
    print("Rendering search results template...")
    return render_template('search_results.html', results=results)
@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    courses = Course.query.all()
    users = User.query.all()
    
    return render_template('admin.html', courses=courses, users=users)
 

# Utility function for file validation (if not already defined)
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/course/<int:course_id>/material/new', methods=['GET', 'POST'])
@login_required
def add_material(course_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)

    if request.method == 'POST':
        title = request.form.get('title')
        file = request.files.get('file')

        # Validate input fields
        if not title or not file:
            flash('Please fill out all fields.', 'danger')
            return render_template('add_material.html', course=course)

        # Check if the uploaded file is valid
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            file_extension = os.path.splitext(original_filename)[1]  # Extract the file extension
            new_filename = secure_filename(f"{title.lower().replace(' ', '_')}{file_extension}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)

            # Save the file to the specified upload folder
            file.save(file_path)

            # Create a new Material instance
            material = Material(
                course_id=course.id,
                title=title,
                type=get_file_type(new_filename),
                file_path=new_filename
            )

            # Add the material to the database and commit the changes
            db.session.add(material)
            db.session.commit()
            flash('Material added successfully!', 'success')
            return redirect(url_for('course_detail', course_id=course.id))  # Ensure this endpoint exists

        flash('Invalid file type', 'danger')

    return render_template('add_material.html', course=course)




@app.route('/download/material/<int:material_id>')
@login_required
def download_material(material_id):
    # Find the material
    material = Material.query.get_or_404(material_id)
    
    # Check if the user is enrolled in the course
    if not current_user.is_admin:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, 
            course_id=material.course_id
        ).first()
        
        if not enrollment:
            flash('You must be enrolled in the course to download materials.', 'danger')
            return redirect(url_for('course_detail', course_id=material.course_id))
    
    # Construct the full file path
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], material.file_path)
    
    # Check if file exists
    if not os.path.exists(file_path):
        abort(404)
    
    try:
        return send_file(
            file_path, 
            as_attachment=True, 
            download_name=material.file_path
        )
    except Exception as e:
        # Log the error
        print(f"Download error: {e}")
        abort(500)
 
@app.route('/admin/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    course = Course.query.get_or_404(course_id)

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        instructor = request.form.get('instructor')

        # Basic validation
        if not title or not description or not instructor:
            flash('Please fill out all fields.', 'danger')
            return render_template('edit_course.html', course=course)

        course.title = title
        course.description = description
        course.instructor = instructor

        # Handle thumbnail upload
        if 'thumbnail' in request.files:
            file = request.files['thumbnail']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                course.thumbnail_path = filename

        db.session.commit()
        flash('Course updated successfully!', 'success')
        return redirect(url_for('admin'))

    return render_template('edit_course.html', course=course)
# In your route or a context processor
@app.context_processor
def utility_processor():
    def get_course_categories():
        return [category.value for category in CourseCategory]
    return dict(course_categories=get_course_categories())
@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])

@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('User  deleted successfully!', 'success')
    else:
        flash('User  not found.', 'danger')

    return redirect(url_for('admin'))
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'mp4', 'webm', 'mp3', 'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    if ext in ['mp4', 'webm']:
        return 'video'
    elif ext in ['mp3']:
        return 'audio'
    elif ext in ['pdf', 'doc', 'docx']:
        return 'document'
    else:
        return 'image'


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Check if admin exists first
        admin = User.query.filter_by(email='admin@nyonks.com').first()
        if not admin:
            try:
                admin = User(
                    username='admin',
                    email='admin@nyonks.com',  # Fixed email format
                    is_admin=True
                )
                admin.set_password('admin')
                db.session.add(admin)
                db.session.commit()
                print("Admin user created successfully")
            except Exception as e:
                db.session.rollback()
                print(f"Admin user creation failed: {e}")
        else:
            print("Admin user already exists")
    
    app.run(debug=True, port= 7337)
