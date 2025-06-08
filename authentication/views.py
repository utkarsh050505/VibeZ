from django.shortcuts import render, redirect
from .models import CoworkingUser as User
from django.http import JsonResponse
from django.contrib import auth
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.core.mail import send_mail
from validate_email import validate_email
from django.urls import reverse
from django.contrib import messages
from .utils import token_generator
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from  django.utils.encoding import force_bytes, force_str
from django.core.cache import cache
import random
import json
import threading

# Create your views here.
class EmailThread(threading.Thread):
    def __init__(self, email_subject, email_body, to_email):
        self.email_subject = email_subject
        self.email_body = email_body
        self.to_email = to_email
        threading.Thread.__init__(self)
    
    def run(self):
        send_mail(
            self.email_subject,
            self.email_body,
            "noreply@semicolon.com",
            [self.to_email],
            fail_silently=False
        )

def send_otp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'error': 'Email is required'}, status=400)
            
            # Validate email format
            if not validate_email(email):
                return JsonResponse({'error': 'Invalid email format'}, status=400)
            
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({'error': 'Email already registered'}, status=400)
            
            # Generate 4-digit OTP
            otp = random.randint(1000, 9999)
            
            # Store OTP in cache for 2 minutes (120 seconds)
            cache_key = f"otp_{email}"
            cache.set(cache_key, otp, 120)  # Changed from 300 to 120 seconds
            
            # Send OTP email
            email_subject = 'Your VibeZone Registration OTP'
            email_body = f'Your OTP for VibeZone registration is: {otp}\n\nThis OTP is valid for 2 minutes.'
            
            EmailThread(email_subject, email_body, email).start()
            
            return JsonResponse({'success': True, 'message': 'OTP sent successfully'})
            
        except Exception as e:
            return JsonResponse({'error': 'Failed to send OTP'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# Add this new function to check OTP validity without verification:
def check_otp_status(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get('email')
            
            if not email:
                return JsonResponse({'error': 'Email is required'}, status=400)
            
            # Check if OTP exists in cache
            cache_key = f"otp_{email}"
            stored_otp = cache.get(cache_key)
            
            if stored_otp:
                return JsonResponse({'valid': True, 'message': 'OTP is still valid'})
            else:
                return JsonResponse({'valid': False, 'message': 'OTP expired'})
                
        except Exception as e:
            return JsonResponse({'error': 'Failed to check OTP status'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def verify_otp(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get('email')
            otp = data.get('otp')
            
            if not email or not otp:
                return JsonResponse({'error': 'Email and OTP are required'}, status=400)
            
            # Get OTP from cache
            cache_key = f"otp_{email}"
            stored_otp = cache.get(cache_key)
            
            if not stored_otp:
                return JsonResponse({'error': 'OTP expired or not found'}, status=400)
            
            if str(stored_otp) == str(otp):
                # OTP is correct, remove from cache
                cache.delete(cache_key)
                return JsonResponse({'success': True, 'message': 'OTP verified successfully'})
            else:
                return JsonResponse({'error': 'Invalid OTP'}, status=400)
                
        except Exception as e:
            return JsonResponse({'error': 'Failed to verify OTP'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def EmailValidation(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data['email']

        if not validate_email(email):
            return JsonResponse({'email_error': 'Please enter valid Email.'}, status=400)
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({'email_error': 'Email already in use.'}, status=409)

        return JsonResponse({"email_valid": True})


def PhoneValidation(request):
    if request.method == "POST":
        data = json.loads(request.body)
        phone = data.get('phone', '')
        
        if not phone.isdigit():
            return JsonResponse({'phone_error': 'Phone number should only contain digits!'}, status=400)
        
        if len(phone) != 10:
            return JsonResponse({'phone_error': 'Phone number should be 10 digits!'}, status=400)
        
        if User.objects.filter(phone=phone).exists():
            return JsonResponse({'phone_error': 'This phone number is already registered.'}, status=409)
        
        return JsonResponse({"phone_valid": True})
    
    return JsonResponse({"error": "Method not allowed"}, status=405)

def signup(request):
    if request.method == 'GET':
        return render(request, 'authentication/signup.html')
    else:
        name = request.POST['name']
        phone = request.POST['phone']
        email = request.POST['email']
        study_level = request.POST['study_level']
        specialization = request.POST['specialization']
        college = request.POST['college']
        password = request.POST['password']
        email_verified = request.POST.get('email_verified', 'false')  # Add this line
        
        # Check if email is verified
        if email_verified != 'true':
            return render(request, 'authentication/signup.html', {
                'message': 'Please verify your email with OTP before registering.'
            })
        
        if not User.objects.filter(phone=phone).exists():
            if not User.objects.filter(email=email).exists():
                
                if len(name) == 0 or len(email) == 0:
                    return render(request, 'authentication/signup.html')
                
                if len(password) < 6:
                    return render(request, 'authentication/signup.html', {
                        'name': name,
                        'email': email,
                        'message': 'Password should be greater than 6 characters',
                    })

                user = User.objects.create(name=name, username=email, email=email, phone=phone, study_level=study_level, specialization=specialization, college_name=college)
                user.set_password(password)
                user.save()
                auth.login(request, user)
                return redirect('home')
            else:
                return render(request, 'authentication/signup.html', {
                    'message': 'Email already registered'
                })
        else:
            return render(request, 'authentication/signup.html', {
                'message': 'Phone number already registered'
            })  

def login(request):
    if request.method == 'GET':
        
        return render(request, 'authentication/login.html')
    
    else:
        
        email = request.POST["email"]
        password = request.POST["password"]
        
        if email and password:
            
            user = auth.authenticate(username=email, password=password)
            
            if user:
                auth.login(request, user)
                print('login')
                return redirect('home')
            else:
                user_exist = User.objects.filter(username=email).exists()
                if user_exist:
                    return render(request, 'authentication/login.html', {
                        "message": "Invalid Credentials, Please try again!"
                    })
                else:
                    return render(request, 'authentication/login.html', {
                        "message": "User does not exist, Please Register!"
                    })

def logout(request):
    if request.method == "POST":
        auth.logout(request)
        return redirect('login')


def reset_password(request):
    if request.method == 'GET':
        return render(request, 'authentication/reset-password.html')
    else:
        email = request.POST["email"]
        print(email)
        
        if not validate_email(email):
            return render(request, "authentication/reset-password.html", {
                'messages': 'Please enter a valid Email!'
            })
        
        user = User.objects.filter(username=email)
        
        if user.exists():

            uidb64 = urlsafe_base64_encode(force_bytes(user[0].pk))
            domain = get_current_site(request).domain
            link = reverse(
                    'set-new-password',
                    kwargs={
                        'uidb64': uidb64,
                        'token': PasswordResetTokenGenerator().make_token(user[0])
                        }
                    )

            reset_url = 'http://' + domain + link

            email_subject = 'Reset your account password'
            email_body = 'Hi there,' + '\n' + 'Please use this link to reset your account password - ' + reset_url

            EmailThread(email_subject, email_body, email).start()
            print(EmailThread)
            
            messages.success(request, "Please check your email to reset your password")
            return render(request, "authentication/reset-password.html")
        else:
            return render(request, 'authentication/reset-password.html', {
                'messages': 'Please enter valid Email',
            })

def complete_reset_password(request, uidb64, token):
    if request.method == 'GET':
        try:
            id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=id)

            if not PasswordResetTokenGenerator().check_token(user, token):
                messages.info(request, "Password link invalid, please try again.")
                return render(request, 'authentication/reset-password.html')
        except Exception as e:
            pass
        
        return render(request, 'authentication/set-new-password.html', {
            'uidb64': uidb64,
            'token': token
        })
    
    else:
        password = request.POST["password"]
        confirmPassword = request.POST["confirmPassword"]
        
        if password != confirmPassword:
            messages.error(request, "Password does not match.")
            return render(request, 'authentication/set-new-password.html', {
                'uidb64': uidb64,
                'token': token
            })
        
        if len(password) < 6:
            messages.error(request, 'Password should be greater than 6 characters')
            return render(request, 'authentication/set-new-password.html', {
                'uidb64': uidb64,
                'token': token
            })
        
        try:
            id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=id)
            user.set_password(password)
            user.save()

            messages.success(request, "Password reset successfully")
            return redirect('login')
        except Exception as e:
            messages.error(request, "An unexpected error occurred, Please try again.")
            return render(request, "authentication/set-new-password.html", {
                'uidb64': uidb64,
                'token': token
            })