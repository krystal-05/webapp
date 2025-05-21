from flask import Flask, redirect, url_for, request, flash, session, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.security import generate_password_hash, check_password_hash
from forms import UpdateProfileForm
import secrets
from PIL import Image 

app = Flask(__name__)
#this protects session data and hard-coding a secret key is risky
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

#table to keep track of users friends 
friends= db.Table('friends',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)            
    #foreign keys are referencing id from User             
)

class User(db.Model):
    id = db.Column("id", db.Integer, primary_key=True) #primary key is always unqiue
    first_name = db.Column(db.String(20), unique=False, nullable=False)
    last_name = db.Column(db.String(20), unique=False, nullable=False)
    email = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), unique=False, nullable=False)
    image_file = db.Column(db.String(50), unique=False, nullable=False, default='default.png')
    friends = db.relationship('User', secondary=friends, primaryjoin=(friends.c.user_id == id),
        secondaryjoin=(friends.c.friend_id == id), backref=db.backref('friend_of', lazy='dynamic'), lazy='dynamic')
    #secondary=friends: uses the friends table to associate the users
    #primaryjoin- tells sql how to match the user to the friend
    #secondaryjoin- tells sql how to match the friend to the user
    #backref creates a reverse relationship 


#Model for friend requests 
class FriendRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='none')  

    requester = db.relationship('User', foreign_keys=[requester_id], backref='sent_requests')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_requests')

with app.app_context(): #needed for db operation
       db.create_all()

@app.route("/")
def index():
    users = User.query.all()
    return render_template('index.html', users=users)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        #get data
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        if password != confirm_password:
            return render_template('register.html', message="Passwords do not match.")
        #hash the password for security
        hashed_password = generate_password_hash(password)
        #save data
        new_user = User(first_name=first_name, last_name=last_name, email=email.lower(), password=hashed_password) #lower() saves email in lowercase
        db.session.add(new_user)
        db.session.commit()
        flash("Successfully registered")
        return redirect(url_for("login"))
    
    else:
        return render_template("register.html")

@app.route("/logout")
def logout():
    #message only displays if there was a user in session 
    if "user" in session:
        user = session["user"]
        session.pop("user", None)
        session.pop("email", None)
        flash("successfully logged out", "info")
        return redirect(url_for("login"))
    else:
        flash("log out failed", "info")
        return redirect(url_for("settings"))

@app.route("/user_page", methods=["POST", "GET"])
def user_page():
    if "user" in session:
        return render_template ("user_page.html", user=session["user"])
    #not logged in
    else:
        flash("You are not logged in")
        return redirect(url_for("login"))
    
@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        email = request.form["email"].lower() #ensures email is submitted in lowercase
        password = request.form["password"]
    

        #fetches one user
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session["user"] = user.id
            flash("Login successful!")
            return redirect(url_for("user_page"))
        else:
            flash("Invalid credentials.")
            return render_template("login.html")

    else:
        return render_template("login.html")

@app.route("/search_users")
def search_users():
    return render_template("search_users.html")

# Route to return the JSON data for fetch()
@app.route("/api_search_users")
def api_search_users():
    if "user" in session:
        users = User.query.all()
        user_id = session.get("user")

        users_data = []
        current_user = User.query.get(user_id) 
        for user in users:
            if user.id == current_user.id:
                continue  #skip current_user

            # Check friendship status
            if user in current_user.friends:
                friend_status = "accepted"
            else:
                # Check if there's a pending request
                pending = FriendRequest.query.filter_by(
                requester_id=user_id, receiver_id=user.id, status="pending"
                ).first()

                if pending:
                    friend_status = "pending"
                else:
                    friend_status = "none"

            users_data.append({
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "friend_status": friend_status
            })
            print(f"Friend status for {user.first_name}: {friend_status}")
        # Return as JSON
        return jsonify(users=users_data)

    else:
        return jsonify({"error": "Not logged in"})

     
@app.route("/send_friend_request/<int:receiver_id>", methods=["POST"])
def send_friend_request(receiver_id):
    if "user" in session:
        user_id = session["user"]
        # Get the full User object
        user = User.query.get(user_id) 
        #get the full receiver object
        receiver = User.query.get(receiver_id)
        new_request = FriendRequest(
        requester_id = user_id,
        receiver_id = receiver_id,
        status = "pending"
    )
        # Don't allow duplicates
        existing_request = FriendRequest.query.filter_by(
        requester_id=user_id,
        receiver_id=receiver_id,
        status="pending"
        ).first()

        if existing_request:
            return jsonify(success=False, message="Friend request already sent.")
        if receiver in user.friends:
            return jsonify(success=False, message="Already friends", new_label="Remove Friend", new_status="friend")

        db.session.add(new_request)
        db.session.commit()
        return jsonify(success=True, new_label="Pending", new_status="pending")
        
    else:
        return jsonify(success=False)

@app.route("/cancel_friend_request/<int:receiver_id>", methods=["POST"])
def cancel_friend_request(receiver_id):
    user_id = session["user"]

    # Find the pending request from user to the receiver
    #you can only use .get if the value is a primary key
    request = FriendRequest.query.filter_by(
        requester_id=user_id,
        receiver_id=receiver_id,
        status="pending"
    ).first()

    if request:
        print(f"Cancelled friend request from user {user_id} to user {receiver_id}")
        db.session.delete(request)
        db.session.commit()
        return jsonify(success=True, new_label="Add Friend", new_status="none")

@app.route("/remove_friend/<int:friend_id>", methods=["POST"])
def remove_friend(friend_id):  
    user_id = session["user"]
    user = User.query.get(user_id)
    friend = User.query.get(friend_id)

    if friend in user.friends:
        user.friends.remove(friend)
        db.session.commit()
        return jsonify(success=True, new_label="Add Friend", new_status="none")
    
    if not user or not friend:
        return jsonify(success=False, message="User not found")

@app.route("/accept_friend/<int:requester_id>", methods=["POST"])
def accept_friend(requester_id):
    print("ACCEPT FRIEND CALLED with:", requester_id)
    user_id = session["user"]
    user = User.query.get(user_id)
    friend = User.query.get(requester_id)

    # Find the pending request from user to the receiver
    #you can only use .get if the value is a primary key
    request = FriendRequest.query.filter_by(
        receiver_id = user_id,
        requester_id = requester_id,
        status="pending"
    ).first()

    
    if friend not in user.friends:
        #status needs to be updated or else the status will stay at pending.
        request.status = "accepted"
        user.friends.append(friend)
        db.session.commit()
        print("worked:", requester_id)
        return jsonify(success=True, new_label="Friends", new_status="accepted")
    
    else:
        return jsonify(success=False, error="No pending request found")
    
@app.route("/reject_friend/<int:requester_id>", methods=["POST"])
def reject_friend(requester_id):
    user_id = session["user"]
    user = User.query.get(user_id)
    friend = User.query.get(requester_id)

    # Find the pending request from user to the receiver
    #you can only use .get if the value is a primary key
    request = FriendRequest.query.filter_by(
        receiver_id = user_id,
        requester_id = requester_id,
        status="pending"
    ).first()

    
    if friend not in user.friends:
        db.session.delete(request)
        db.session.commit()
        return jsonify(success=True, new_label="Add Friend", new_status="none")
    
    else:
        return jsonify(success=False, error="No pending request found")
    
    
@app.route("/show_friend_requests")
def show_friend_requests():
    receiver_id = session["user"]
    requests = FriendRequest.query.filter_by(receiver_id=receiver_id, status="pending").all()

    #displays all friend requests
    users = []
    
    for request in requests:
        requester = User.query.get(request.requester_id)
        users.append({
                "id": requester.id,
                "first_name": requester.first_name,
                "last_name": requester.last_name,
                "friend_status": request.status
        })

    return jsonify(users=users)

#this is neccessary to run the html template. IT WILL NOT RUN WITHOUT THIS!!!!
@app.route("/show_requests")
def showrequest():
    return render_template("friend_requests.html")

@app.route("/profile")
def profile():
    # Get the full User object
    user_id = session["user"]
    user = User.query.get(user_id) 
    image_file = url_for('static', filename='proile_pics/' + user.image_file)

    return render_template('profile.html', image_file=image_file)

def save_picture(form_picture):
    #do this so the name of the users pic doesn't accidentally colide with an image already in folder
    #-randomizes name of image
    random_hex = secrets.token_hex(8) 
    #returns filename and the extension
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_filename = random_hex + f_ext
    #save to static folder
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_filename)

    #resize image to fit profile bubble- 125px
    output_size = (125,125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    #save to picture_path
    i.save(picture_path)
    
    return picture_filename

@app.route("/updateProfile", methods=["GET", "POST"])
def update_profile():
     # Get the full User object
    user_id = session["user"]
    user = User.query.get(user_id) 
    form = UpdateAccountForm()

    #pre-fill with current account data
    if request.method == "GET":
        form.first_name.data = user.first_name
        form.last_name.data = user.last_name
        form.image_file.data = user.image_file 

    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            user.image_file = picture_file 

        #update password - user enters old password first for security 
        # Check if the current password is correct
        if not check_password_hash(user.password, form.current_password.data):
            flash("Incorrect current password.", "danger")
            return redirect(url_for("update_profile"))
        
        if form.password.data:
            if form.password.data == form.confirm_password.data:  
                hashed_password = generate_password_hash(form.password.data)
                user.password = hashed_password
            else:
                flash("Passwords do not match.", "danger")
                return redirect(url_for("update_profile")) 

        db.session.commit()
        

        flash("Your account has been updated!", "success")
        return redirect(url_for("profile"))  # Redirect to a page (like profile page)
    
    return render_template("update_profile.html", form=form)


if __name__ == "__main__":
    app.run()
