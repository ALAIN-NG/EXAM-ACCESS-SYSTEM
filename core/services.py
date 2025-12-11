from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q, Count
import qrcode
import io
from django.core.files.base import ContentFile
from PIL import Image
import base64
import json
from datetime import timedelta

from .models import (
    Etudiant, Examen, ControleAcces, InscriptionUE,
    Paiement, JustificatifAbsence, AuditLog, SessionExamen
)


class QRCodeService:
    """Service pour la génération et validation des QR codes"""
    
    @staticmethod
    def generate_qr_code(etudiant):
        """Générer un QR code pour un étudiant"""
        # Créer les données à encoder
        qr_data = {
            'matricule': etudiant.matricule,
            'qr_token': str(etudiant.qr_token),
            'nom': etudiant.nom,
            'prenom': etudiant.prenom,
            'timestamp': timezone.now().isoformat()
        }
        
        # Convertir en JSON
        qr_json = json.dumps(qr_data)
        
        # Générer le QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_json)
        qr.make(fit=True)
        
        # Créer l'image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Sauvegarder dans un buffer
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Convertir en base64 pour l'API
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            'qr_code': qr_base64,
            'qr_data': qr_data,
            'etudiant': {
                'matricule': etudiant.matricule,
                'nom': etudiant.nom,
                'prenom': etudiant.prenom,
                'filiere': etudiant.filiere.nom if etudiant.filiere else None,
                'niveau': etudiant.niveau.nom if etudiant.niveau else None
            }
        }
    
    @staticmethod
    def validate_qr_code(qr_data, examen):
        """Valider un QR code scanné"""
        try:
            # Parser les données du QR code
            data = json.loads(qr_data)
            
            # Vérifier les champs requis
            required_fields = ['matricule', 'qr_token']
            for field in required_fields:
                if field not in data:
                    return False, f"Champ manquant: {field}"
            
            # Récupérer l'étudiant
            try:
                etudiant = Etudiant.objects.get(
                    matricule=data['matricule'],
                    qr_token=data['qr_token']
                )
            except Etudiant.DoesNotExist:
                return False, "Étudiant non trouvé ou token invalide"
            
            # Vérifier le statut de l'étudiant
            if etudiant.statut != 'actif':
                return False, f"Étudiant {etudiant.get_statut_display()}"
            
            # Vérifier le paiement
            paiement = Paiement.objects.filter(
                etudiant=etudiant,
                annee_academique=examen.annee_academique,
                est_regle=True
            ).exists()
            
            if not paiement:
                return False, "Paiement non réglé"
            
            # Vérifier l'inscription et l'autorisation
            inscription = InscriptionUE.objects.filter(
                etudiant=etudiant,
                ue=examen.ue,
                annee_academique=examen.annee_academique,
                est_autorise_examen=True
            ).exists()
            
            if not inscription:
                return False, "Non inscrit ou non autorisé pour cet examen"
            
            # Vérifier l'horaire
            maintenant = timezone.now()
            debut_examen = timezone.make_aware(
                timezone.datetime.combine(examen.date, examen.heure_debut)
            )
            fin_examen = timezone.make_aware(
                timezone.datetime.combine(examen.date, examen.heure_fin)
            )
            
            # Tolérance de 30 minutes
            if maintenant < debut_examen - timedelta(minutes=30):
                return False, "Trop tôt pour l'examen"
            elif maintenant > fin_examen + timedelta(minutes=30):
                return False, "Examen déjà terminé"
            
            # Vérifier si déjà scanné
            deja_scanne = ControleAcces.objects.filter(
                examen=examen,
                etudiant=etudiant
            ).exists()
            
            if deja_scanne:
                return False, "Déjà scanné pour cet examen"
            
            return True, "QR code valide"
            
        except json.JSONDecodeError:
            return False, "QR code invalide (format JSON incorrect)"
        except Exception as e:
            return False, f"Erreur de validation: {str(e)}"


class ExamenService:
    """Service pour la gestion des examens"""
    
    @staticmethod
    def get_examens_du_jour(user=None):
        """Récupérer les examens du jour"""
        aujourdhui = timezone.now().date()
        queryset = Examen.objects.filter(date=aujourdhui)
        
        # Filtrer par surveillant si c'est un surveillant
        if user and user.groups.filter(name='Surveillant').exists():
            queryset = queryset.filter(surveillant=user)
        
        return queryset.select_related(
            'ue', 'ue__filiere', 'salle', 'surveillant', 'session'
        ).order_by('heure_debut')
    
    @staticmethod
    def get_statistiques_examen(examen):
        """Récupérer les statistiques d'un examen"""
        total_inscrits = InscriptionUE.objects.filter(
            ue=examen.ue,
            annee_academique=examen.annee_academique,
            est_autorise_examen=True
        ).count()
        
        total_presents = ControleAcces.objects.filter(
            examen=examen,
            autorise=True
        ).count()
        
        total_refuses = ControleAcces.objects.filter(
            examen=examen,
            autorise=False
        ).count()
        
        total_absents = total_inscrits - total_presents - total_refuses
        
        return {
            'total_inscrits': total_inscrits,
            'total_presents': total_presents,
            'total_refuses': total_refuses,
            'total_absents': total_absents,
            'taux_presence': round((total_presents / total_inscrits * 100), 2) if total_inscrits > 0 else 0
        }
    
    @staticmethod
    @transaction.atomic
    def creer_examen(data, created_by):
        """Créer un examen avec validation"""
        # Vérifier les conflits d'horaire
        conflits = Examen.objects.filter(
            salle=data['salle'],
            date=data['date'],
        ).exclude(pk=data.get('id'))
        
        for conflit in conflits:
            if (data['heure_debut'] < conflit.heure_fin and 
                data['heure_fin'] > conflit.heure_debut):
                raise ValidationError(
                    f"Conflit d'horaire avec l'examen {conflit.ue.code} "
                    f"({conflit.heure_debut}-{conflit.heure_fin})"
                )
        
        # Créer l'examen
        examen = Examen.objects.create(**data)
        examen.created_by = created_by
        examen.save()
        
        # Log l'action
        AuditLog.objects.create(
            utilisateur=created_by,
            action_type='examen',
            action=f"Création examen {examen.ue.code} - {examen.date}",
            details={
                'examen_id': examen.id,
                'ue': examen.ue.code,
                'date': examen.date.isoformat(),
                'salle': examen.salle.code if examen.salle else None
            }
        )
        
        return examen


class ScanService:
    """Service pour la gestion des scans"""
    
    @staticmethod
    @transaction.atomic
    def scanner_etudiant(examen_id, scan_data, scanned_by):
        """Scanner un étudiant pour un examen"""
        try:
            examen = Examen.objects.get(id=examen_id)
        except Examen.DoesNotExist:
            raise ValidationError("Examen non trouvé")
        
        method = scan_data.get('method', 'qr')
        matricule = scan_data.get('matricule')
        qr_data = scan_data.get('qr_data')
        
        # Identifier l'étudiant
        if method == 'qr' and qr_data:
            # Validation QR code
            is_valid, message = QRCodeService.validate_qr_code(qr_data, examen)
            
            if not is_valid:
                # Créer un contrôle d'accès refusé
                controle = ControleAcces.objects.create(
                    examen=examen,
                    etudiant=None,  # Étudiant non identifié
                    scan_method='qr',
                    autorise=False,
                    raison_refus=message,
                    scanned_by=scanned_by
                )
                
                # Log l'action
                AuditLog.objects.create(
                    utilisateur=scanned_by,
                    action_type='scan',
                    action=f"Scan QR refusé: {message}",
                    details={
                        'examen_id': examen.id,
                        'raison': message,
                        'method': 'qr'
                    }
                )
                
                return {
                    'success': False,
                    'message': message,
                    'controle_id': controle.id
                }
            
            # Récupérer l'étudiant depuis le QR code
            data = json.loads(qr_data)
            etudiant = Etudiant.objects.get(
                matricule=data['matricule'],
                qr_token=data['qr_token']
            )
            
        elif method == 'matricule' and matricule:
            # Recherche par matricule
            try:
                etudiant = Etudiant.objects.get(matricule=matricule)
            except Etudiant.DoesNotExist:
                controle = ControleAcces.objects.create(
                    examen=examen,
                    etudiant=None,
                    scan_method='matricule',
                    autorise=False,
                    raison_refus="Matricule non trouvé",
                    scanned_by=scanned_by
                )
                
                return {
                    'success': False,
                    'message': "Matricule non trouvé",
                    'controle_id': controle.id
                }
            
            # Vérifications manuelles
            is_valid, message = ScanService._valider_etudiant_manuel(etudiant, examen)
            
            if not is_valid:
                controle = ControleAcces.objects.create(
                    examen=examen,
                    etudiant=etudiant,
                    scan_method='matricule',
                    autorise=False,
                    raison_refus=message,
                    scanned_by=scanned_by
                )
                
                return {
                    'success': False,
                    'message': message,
                    'controle_id': controle.id,
                    'etudiant': {
                        'matricule': etudiant.matricule,
                        'nom': etudiant.nom,
                        'prenom': etudiant.prenom
                    }
                }
        
        else:
            raise ValidationError("Méthode de scan invalide")
        
        # Créer le contrôle d'accès
        controle = ControleAcces.objects.create(
            examen=examen,
            etudiant=etudiant,
            scan_method=method,
            autorise=True,
            scanned_by=scanned_by
        )
        
        # Log l'action
        AuditLog.objects.create(
            utilisateur=scanned_by,
            action_type='scan',
            action=f"Scan réussi pour {etudiant.matricule} - {examen.ue.code}",
            details={
                'etudiant_id': etudiant.id,
                'examen_id': examen.id,
                'method': method,
                'autorise': True
            },
            content_object=controle
        )
        
        return {
            'success': True,
            'message': "Accès autorisé",
            'controle_id': controle.id,
            'etudiant': {
                'matricule': etudiant.matricule,
                'nom': etudiant.nom,
                'prenom': etudiant.prenom,
                'photo_url': etudiant.photo.url if etudiant.photo else None
            },
            'examen': {
                'ue': examen.ue.code,
                'date': examen.date,
                'heure_debut': examen.heure_debut,
                'heure_fin': examen.heure_fin
            }
        }
    
    @staticmethod
    def _valider_etudiant_manuel(etudiant, examen):
        """Validation manuelle d'un étudiant (pour scan matricule)"""
        # Vérifier le statut
        if etudiant.statut != 'actif':
            return False, f"Étudiant {etudiant.get_statut_display()}"
        
        # Vérifier le paiement
        paiement = Paiement.objects.filter(
            etudiant=etudiant,
            annee_academique=examen.annee_academique,
            est_regle=True
        ).exists()
        
        if not paiement:
            return False, "Paiement non réglé"
        
        # Vérifier l'inscription
        inscription = InscriptionUE.objects.filter(
            etudiant=etudiant,
            ue=examen.ue,
            annee_academique=examen.annee_academique,
            est_autorise_examen=True
        ).exists()
        
        if not inscription:
            return False, "Non inscrit ou non autorisé"
        
        # Vérifier l'horaire
        maintenant = timezone.now()
        debut_examen = timezone.make_aware(
            timezone.datetime.combine(examen.date, examen.heure_debut)
        )
        fin_examen = timezone.make_aware(
            timezone.datetime.combine(examen.date, examen.heure_fin)
        )
        
        if maintenant < debut_examen - timedelta(minutes=30):
            return False, "Trop tôt pour l'examen"
        elif maintenant > fin_examen + timedelta(minutes=30):
            return False, "Examen déjà terminé"
        
        # Vérifier si déjà scanné
        if ControleAcces.objects.filter(examen=examen, etudiant=etudiant).exists():
            return False, "Déjà scanné pour cet examen"
        
        return True, "Validation réussie"
    
    @staticmethod
    def get_scans_examen(examen_id, user):
        """Récupérer les scans d'un examen"""
        queryset = ControleAcces.objects.filter(examen_id=examen_id)
        
        # Si c'est un surveillant, ne voir que ses scans
        if user.groups.filter(name='Surveillant').exists():
            queryset = queryset.filter(scanned_by=user)
        
        return queryset.select_related(
            'etudiant', 'examen', 'examen__ue', 'scanned_by'
        ).order_by('-date_scan')


class ReportingService:
    """Service pour les rapports et statistiques"""
    
    @staticmethod
    def generate_presence_report(examen_id):
        """Générer un rapport de présence pour un examen"""
        examen = Examen.objects.get(id=examen_id)
        
        # Récupérer tous les étudiants inscrits
        inscriptions = InscriptionUE.objects.filter(
            ue=examen.ue,
            annee_academique=examen.annee_academique,
            est_autorise_examen=True
        ).select_related('etudiant')
        
        # Récupérer les scans
        scans = ControleAcces.objects.filter(examen=examen).select_related('etudiant')
        scans_dict = {scan.etudiant_id: scan for scan in scans}
        
        # Préparer le rapport
        rapport = {
            'examen': {
                'ue': examen.ue.code,
                'intitule': examen.ue.intitule,
                'date': examen.date,
                'heure_debut': examen.heure_debut,
                'heure_fin': examen.heure_fin,
                'salle': examen.salle.code if examen.salle else None
            },
            'presences': [],
            'statistiques': {
                'total_inscrits': len(inscriptions),
                'total_presents': 0,
                'total_absents': 0,
                'total_refuses': 0
            }
        }
        
        for inscription in inscriptions:
            etudiant = inscription.etudiant
            scan = scans_dict.get(etudiant.id)
            
            presence_data = {
                'matricule': etudiant.matricule,
                'nom': etudiant.nom,
                'prenom': etudiant.prenom,
                'present': False,
                'autorise': False,
                'heure_scan': None,
                'methode_scan': None,
                'raison_refus': None
            }
            
            if scan:
                presence_data.update({
                    'present': True,
                    'autorise': scan.autorise,
                    'heure_scan': scan.date_scan,
                    'methode_scan': scan.get_scan_method_display(),
                    'raison_refus': scan.raison_refus
                })
                
                if scan.autorise:
                    rapport['statistiques']['total_presents'] += 1
                else:
                    rapport['statistiques']['total_refuses'] += 1
            else:
                presence_data['raison_refus'] = "Absent"
                rapport['statistiques']['total_absents'] += 1
            
            rapport['presences'].append(presence_data)
        
        return rapport
    
    @staticmethod
    def generate_statistiques_globales(annee_academique_id=None):
        """Générer des statistiques globales"""
        from django.db.models import Count, Avg
        
        # Filtre par année académique
        filters = {}
        if annee_academique_id:
            filters['annee_academique_id'] = annee_academique_id
        
        # Statistiques de base
        stats = {
            'total_etudiants': Etudiant.objects.count(),
            'etudiants_actifs': Etudiant.objects.filter(statut='actif').count(),
            'total_examens': Examen.objects.filter(**filters).count(),
            'examens_aujourdhui': Examen.objects.filter(date=timezone.now().date()).count(),
            'total_scans': ControleAcces.objects.filter(**filters).count(),
            'scans_autorises': ControleAcces.objects.filter(autorise=True, **filters).count(),
            'scans_refuses': ControleAcces.objects.filter(autorise=False, **filters).count(),
        }
        
        # Taux de présence par filière
        stats['presence_par_filiere'] = list(
            Examen.objects.filter(**filters)
            .values('ue__filiere__nom')
            .annotate(
                total_examens=Count('id'),
                taux_presence=Avg('controleacces__autorise')
            )
        )
        
        return stats