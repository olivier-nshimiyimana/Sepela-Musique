import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth import get_user_model
User = get_user_model
from .models import User as artistsUser
from django.contrib import auth


from .forms import RegistrationForm


def register_user(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        data = {'email': email, 'password2': password2, 'password1': password1}
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(password1)
            form.save()
            return JsonResponse({"status": True, "message": "Registration confirm"})
        else:
            errors = []
            for field in form:
                for error in field.errors:
                    errors.append(error)
            return JsonResponse({"status": False, "errors": errors})
    else:
        return render(request, "register.html")


def login_user(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        data = {'email': email, 'password': password}
        user = authenticate(email=email, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return JsonResponse({"status": True, "message": "User logged in"})
            elif user.is_superuser:
                return redirect('publish_list_details')

        else:
            errors = ["User doesn't exists"]
            return JsonResponse({"status": False, "errors": errors})
    else:
        return render(request, "login.html")


def logout_user(request):
    logout(request)
    return redirect('core:home')





def view_function(request): 
    if request.user.is_authenticated: 
        if request.user.is_staff: 
            return redirect('admin_page') 
        elif request.user.is_instructor: 
            return redirect('instructor_page') 
        elif request.user.is_student: 
            return redirect('student_page') 
        else: return redirect('normal_user_page')
    else: return redirect('login_page')
    

  




@login_required
def list_of_artist(request):
    if request.user.user_type != 1:
        return redirect(reverse('core:home'))
    artists = artistsUser.objects.filter(user_type=2).order_by('first_name', 'last_name')
    return render(request, 'artistlist.html', {'artists': artists})


