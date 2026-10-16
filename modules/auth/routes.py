from flask import Blueprint, jsonify, request
from extensions import db, bcrypt
from modules.auth.models import users
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    fullName = data.get('fullName') or data.get('name')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get("confirmPassword") or data.get("confirm_password")

    if not fullName or not email or not password:
        return jsonify({'message': 'Name, email, and password are required!'}), 400

    if confirm_password and password != confirm_password:
        return jsonify({"message": "Password and Confirm Password do not match!"}), 400

    if users.query.filter(users.email == email).first():
        return jsonify({'message': 'Email already exists!'}), 400

    try:
        hashed_password = bcrypt.generate_password_hash(
            password).decode('utf-8')

        new_user = users(
            fullName=fullName.strip(),
            email=email.strip().lower(),
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            "user": {
                "id": new_user.id,
                "fullName": new_user.fullName,
                "name": new_user.fullName,
                "email": new_user.email
            },
            'message': 'User Created successfully!'
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Registration failed!', 'error': str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required!"}), 400

    user = users.query.filter(users.email == email.strip().lower()).first()

    if not user:
        return jsonify({"message": "User not found! please register"}), 404

    if bcrypt.check_password_hash(user.password, password):
        token = create_access_token(
            identity=str(user.id),
            additional_claims={"email": user.email}
        )
        return jsonify({
            "id": user.id,
            "message": "User loggedin successful!",
            "token": token,
            "fullName": user.fullName,
            "name": user.fullName,
            "email": user.email,
            "isLoggedIn": True
        }), 200
    else:
        return jsonify({"message": "Invalid password!"}), 401


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    current_identity = get_jwt_identity()
    try:
        user_id = int(current_identity)
    except (ValueError, TypeError):
        if isinstance(current_identity, dict):
            user_id = current_identity.get("id")
        else:
            user_id = current_identity

    user = users.query.filter_by(id=user_id).first()

    if not user:
        return jsonify({"message": "User not found!"}), 404

    user_data = {
        "id": user.id,
        "name": user.fullName,
        "fullName": user.fullName,
        "email": user.email
    }

    return jsonify({"user": user_data}), 200


