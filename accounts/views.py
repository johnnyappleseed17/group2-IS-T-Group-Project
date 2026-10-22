from django.shortcuts import render

def dashboard(request):
    role = request.user.profile.role
    if role == 'manager':
        return render(request,'accounts/manager_dash.html', context={'role':role})
    return render(request, 'accounts/employee_dash.html', context={'role':role})