from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Etudiant
from .models import JustificatifAbsence
from django.utils import timezone


class StudentLoginForm(forms.Form):
    matricule = forms.CharField(
        max_length=20,
        label='Matricule',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre matricule (ex: ETU001)',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre mot de passe'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        matricule = cleaned_data.get('matricule')
        password = cleaned_data.get('password')
        
        if matricule and password:
            try:
                # Trouver l'étudiant par matricule
                etudiant = Etudiant.objects.get(matricule=matricule)
                
                # Vérifier si l'étudiant a un compte utilisateur
                if not hasattr(etudiant, 'user') or etudiant.user is None:
                    # Si pas d'utilisateur, en créer un automatiquement
                    user = self.create_student_user(etudiant, password)
                    if user:
                        self.user = user
                        self.etudiant = etudiant
                        return cleaned_data
                    else:
                        # Essayer d'authentifier avec le mot de passe initial
                        user = self.authenticate_initial_password(etudiant, password)
                        if user:
                            self.user = user
                            self.etudiant = etudiant
                            return cleaned_data
                        else:
                            raise forms.ValidationError(
                                "Impossible de créer ou d'authentifier votre compte. "
                                "Contactez l'administration."
                            )
                
                # Authentifier l'utilisateur associé
                user = authenticate(
                    username=etudiant.user.username,
                    password=password
                )
                
                if user is None:
                    # Essayer avec le matricule comme username
                    user = authenticate(
                        username=matricule.lower(),
                        password=password
                    )
                
                if user is None:
                    raise forms.ValidationError(
                        "Matricule ou mot de passe incorrect."
                    )
                
                if not user.is_active:
                    raise forms.ValidationError(
                        "Ce compte est désactivé. Contactez l'administration."
                    )
                
                # Vérifier le statut de l'étudiant
                if etudiant.statut != 'actif':
                    raise forms.ValidationError(
                        f"Votre compte étudiant est {etudiant.get_statut_display()}. "
                        "Contactez l'administration."
                    )
                
                self.user = user
                self.etudiant = etudiant
                
            except Etudiant.DoesNotExist:
                raise forms.ValidationError(
                    "Matricule non trouvé. Vérifiez votre saisie."
                )
            
        return cleaned_data
    
    def create_student_user(self, etudiant, password):
        """Créer un utilisateur Django pour un étudiant"""
        try:
            # Générer un nom d'utilisateur
            username = f"etu_{etudiant.matricule.lower()}"
            
            # Vérifier si l'utilisateur existe déjà
            try:
                user = User.objects.get(username=username)
                # Associer l'utilisateur existant à l'étudiant
                etudiant.user = user
                etudiant.save()
                return user
            except User.DoesNotExist:
                # Créer un nouvel utilisateur
                user = User.objects.create_user(
                    username=username,
                    email=etudiant.email or f"{username}@ecole.edu",
                    password=password,  # Le mot de passe fourni par l'étudiant
                    first_name=etudiant.prenom,
                    last_name=etudiant.nom,
                    is_active=True
                )
                
                # Ajouter au groupe "Etudiant"
                from django.contrib.auth.models import Group
                etudiant_group, _ = Group.objects.get_or_create(name='Etudiant')
                user.groups.add(etudiant_group)
                
                # Associer l'utilisateur à l'étudiant
                etudiant.user = user
                etudiant.save()
                
                return user
        except Exception as e:
            print(f"Erreur création utilisateur: {e}")
            return None
    
    def authenticate_initial_password(self, etudiant, password):
        """Authentifier avec le mot de passe initial (date de naissance)"""
        try:
            # Essayer avec la date de naissance comme mot de passe
            if etudiant.date_naissance:
                # Format: JJMMAAAA
                initial_password = etudiant.date_naissance.strftime("%d%m%Y")
                
                # Créer l'utilisateur si nécessaire
                username = f"etu_{etudiant.matricule.lower()}"
                
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    user = User.objects.create_user(
                        username=username,
                        email=etudiant.email or f"{username}@ecole.edu",
                        password=initial_password,
                        first_name=etudiant.prenom,
                        last_name=etudiant.nom,
                        is_active=True
                    )
                    
                    # Ajouter au groupe "Etudiant"
                    from django.contrib.auth.models import Group
                    etudiant_group, _ = Group.objects.get_or_create(name='Etudiant')
                    user.groups.add(etudiant_group)
                
                # Associer l'utilisateur à l'étudiant
                etudiant.user = user
                etudiant.save()
                
                # Vérifier le mot de passe
                if user.check_password(initial_password) or user.check_password(password):
                    return user
        except Exception as e:
            print(f"Erreur authentification initiale: {e}")
        
        return None



class JustificatifForm(forms.ModelForm):
    class Meta:
        model = JustificatifAbsence
        fields = ['examen', 'type_justificatif', 'fichier', 'description']
        widgets = {
            'examen': forms.Select(attrs={'class': 'form-control'}),
            'type_justificatif': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Décrivez brièvement la raison de votre absence...'
            }),
            'fichier': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'examen': 'Examen concerné',
            'type_justificatif': 'Type de justificatif',
            'fichier': 'Document justificatif',
            'description': 'Description'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limiter les examens à ceux auxquels l'étudiant est inscrit
        if 'examen' in self.fields:
            self.fields['examen'].queryset = self.fields['examen'].queryset.filter(
                date__gte=timezone.now().date()
            ).order_by('date')
    
    def clean_fichier(self):
        fichier = self.cleaned_data.get('fichier')
        if fichier:
            # Vérifier la taille (max 10MB)
            max_size = 10 * 1024 * 1024
            if fichier.size > max_size:
                raise forms.ValidationError(
                    "Le fichier est trop volumineux. Taille maximum: 10MB."
                )
            
            # Vérifier l'extension
            allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
            ext = fichier.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(
                    f"Extension non autorisée. Extensions autorisées: {', '.join(allowed_extensions)}"
                )
        
        return fichier
    


class UniversalLoginForm(forms.Form):
    username = forms.CharField(
        label='Identifiant',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Matricule, email ou nom d\'utilisateur',
            'autofocus': True
        })
    )
    
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre mot de passe'
        })
    )
    
    user_type = forms.ChoiceField(
        label='Je suis',
        choices=[
            ('auto', 'Je ne sais pas'),
            ('etudiant', 'Étudiant'),
            ('personnel', 'Personnel/Enseignant'),
            # ('admin', 'Administrateur'),
        ],
        initial='auto',
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )