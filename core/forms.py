from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import (
    AnneeAcademique, Filiere, Niveau, UE, Etudiant,
    Paiement, InscriptionUE, Salle, SessionExamen, Examen,
    JustificatifAbsence
)
from django.utils import timezone
from django.core.exceptions import ValidationError


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



class UserProfileForm(forms.ModelForm):
    """Formulaire pour la mise à jour du profil utilisateur"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        labels = {
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'email': 'Adresse email',
            'username': "Nom d'utilisateur",
        }
        help_texts = {
            'username': 'Requis. 150 caractères maximum. Lettres, chiffres et @/./+/-/_ uniquement.',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajouter des classes Bootstrap aux champs
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': f'Entrez votre {self.Meta.labels.get(field_name, field_name)}'
            })
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Vérifier si l'email existe déjà pour un autre utilisateur
            if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                raise ValidationError('Cette adresse email est déjà utilisée.')
        return email
    


class AnneeAcademiqueForm(forms.ModelForm):
    class Meta:
        model = AnneeAcademique
        fields = ['code', 'active']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 2024-2025'
            }),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
    
    def clean_code(self):
        code = self.cleaned_data['code']
        if not len(code) == 9 and '-' in code:
            raise ValidationError("Le format doit être AAAA-AAAA")
        return code

class FiliereForm(forms.ModelForm):
    class Meta:
        model = Filiere
        fields = ['nom', 'code']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la filière'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code abrégé (ex: INF)'
            })
        }

class NiveauForm(forms.ModelForm):
    class Meta:
        model = Niveau
        fields = ['nom', 'ordre']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: L1, L2, M1'
            }),
            'ordre': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            })
        }

class UEForm(forms.ModelForm):
    class Meta:
        model = UE
        fields = ['code', 'intitule', 'filiere', 'niveau', 'semestre', 'credit']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code UE (ex: INF101)'
            }),
            'intitule': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Intitulé de l\'UE'
            }),
            'filiere': forms.Select(attrs={'class': 'form-control'}),
            'niveau': forms.Select(attrs={'class': 'form-control'}),
            'semestre': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 2
            }),
            'credit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 30
            })
        }

class EtudiantForm(forms.ModelForm):
    class Meta:
        model = Etudiant
        fields = [
            'matricule', 'nom', 'prenom', 'email', 'telephone',
            'date_naissance', 'statut', 'filiere', 'niveau', 'photo'
        ]
        widgets = {
            'matricule': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Matricule étudiant'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de famille'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+237 6XX XX XX XX'
            }),
            'date_naissance': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'filiere': forms.Select(attrs={'class': 'form-control'}),
            'niveau': forms.Select(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'})
        }

class PaiementForm(forms.ModelForm):
    class Meta:
        model = Paiement
        fields = ['etudiant', 'annee_academique', 'montant', 'montant_attendu', 'est_regle', 'date_paiement']
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'annee_academique': forms.Select(attrs={'class': 'form-control'}),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'montant_attendu': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'est_regle': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'date_paiement': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            })
        }

class InscriptionUEForm(forms.ModelForm):
    class Meta:
        model = InscriptionUE
        fields = ['etudiant', 'ue', 'annee_academique', 'est_autorise_examen']
        widgets = {
            'etudiant': forms.Select(attrs={'class': 'form-control'}),
            'ue': forms.Select(attrs={'class': 'form-control'}),
            'annee_academique': forms.Select(attrs={'class': 'form-control'}),
            'est_autorise_examen': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class SalleForm(forms.ModelForm):
    class Meta:
        model = Salle
        fields = ['code', 'capacite', 'batiment', 'etage']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code salle (ex: S1)'
            }),
            'capacite': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Nombre de places'
            }),
            'batiment': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bâtiment'
            }),
            'etage': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Étage'
            })
        }

class SessionExamenForm(forms.ModelForm):
    class Meta:
        model = SessionExamen
        fields = ['nom', 'type_session', 'annee_academique', 'date_debut', 'date_fin', 'active']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la session'
            }),
            'type_session': forms.Select(attrs={'class': 'form-control'}),
            'annee_academique': forms.Select(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_fin': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class ExamenForm(forms.ModelForm):
    class Meta:
        model = Examen
        fields = [
            'ue', 'annee_academique', 'session', 'date',
            'heure_debut', 'heure_fin', 'type_examen', 'salle', 'surveillant'
        ]
        widgets = {
            'ue': forms.Select(attrs={'class': 'form-control'}),
            'annee_academique': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'heure_debut': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'heure_fin': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'type_examen': forms.Select(attrs={'class': 'form-control'}),
            'salle': forms.Select(attrs={'class': 'form-control'}),
            'surveillant': forms.Select(attrs={'class': 'form-control'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrer les surveillants pour exclure ceux dont le username commence par "etu"
        self.fields['surveillant'].queryset = User.objects.filter(
            username__startswith='sur'
        ).order_by('last_name', 'first_name')