from django.utils import timezone

def global_context(request):
    """Contexte global disponible dans tous les templates"""
    context = {
        'current_year': timezone.now().year,
        'app_name': 'SG Examens',
        'app_version': '1.0.0',
    }
    
    if request.user.is_authenticated:
        if hasattr(request.user, 'etudiant_profile'):
            context['user_role'] = 'etudiant'
            context['etudiant'] = request.user.etudiant_profile
        elif request.user.groups.filter(name='Surveillant').exists():
            context['user_role'] = 'surveillant'
        elif request.user.groups.filter(name='Enseignant').exists():
            context['user_role'] = 'enseignant'
        elif request.user.groups.filter(name='Administrateur').exists():
            context['user_role'] = 'administrateur'
        elif request.user.is_staff:
            context['user_role'] = 'admin'
    
    return context