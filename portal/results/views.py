from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def results_list(request):
    """List analysis results"""
    return render(request, 'results/results_list.html', {})
