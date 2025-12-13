# core/management/commands/update_exam_dates.py
from datetime import datetime, time, timedelta
import random
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Examen, SessionExamen, UE


class Command(BaseCommand):
    help = 'Met à jour les dates des examens pour commencer le 12 décembre 2025'
    
    # Date de début des examens : 12 décembre 2025
    DATE_DEBUT_EXAMENS = datetime(2025, 12, 12)
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait modifié sans effectuer les changements'
        )
        parser.add_argument(
            '--recreate',
            action='store_true',
            help='Recrée tous les examens avec les nouvelles dates'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        recreate = options['recreate']
        
        self.stdout.write(self.style.SUCCESS('📅 Mise à jour des dates d\'examens...'))
        self.stdout.write(f"Date de début fixée au: {self.DATE_DEBUT_EXAMENS.date()}")
        self.stdout.write(f"Le 13 décembre sera également utilisé pour les examens")
        
        try:
            with transaction.atomic():
                # 1. Mettre à jour les sessions d'examen
                self.update_sessions(dry_run)
                
                # 2. Mettre à jour les dates des examens
                if recreate:
                    self.recreate_examens(dry_run)
                else:
                    self.update_examens(dry_run)
                
                if dry_run:
                    self.stdout.write(self.style.WARNING('⚠️  Mode dry-run: Aucun changement n\'a été effectué'))
                    transaction.set_rollback(True)
                else:
                    self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
                    self.stdout.write(self.style.SUCCESS('✅ DATES D\'EXAMENS MISES À JOUR AVEC SUCCÈS!'))
                    self.stdout.write(self.style.SUCCESS('=' * 60))
                
                # Afficher le résumé
                self.print_summary()
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la mise à jour: {e}"))
            import traceback
            traceback.print_exc()
    
    def update_sessions(self, dry_run):
        """Met à jour les dates des sessions d'examen"""
        self.stdout.write("\n📋 Mise à jour des sessions d'examen...")
        
        # Mettre à jour la session normale
        session_normale = SessionExamen.objects.filter(
            type_session='normale'
        ).first()
        
        if session_normale:
            date_debut = self.DATE_DEBUT_EXAMENS.date()
            date_fin = date_debut + timedelta(days=21)  # 3 semaines
            
            self.stdout.write(f"  Session Normale:")
            self.stdout.write(f"    Ancienne: {session_normale.date_debut} → {session_normale.date_fin}")
            self.stdout.write(f"    Nouvelle: {date_debut} → {date_fin}")
            
            if not dry_run:
                session_normale.date_debut = date_debut
                session_normale.date_fin = date_fin
                session_normale.nom = f'Session Normale {date_debut.year}-{date_fin.year}'
                session_normale.save()
        
        # Mettre à jour la session de rattrapage
        session_rattrapage = SessionExamen.objects.filter(
            type_session='rattrapage'
        ).first()
        
        if session_rattrapage and session_normale:
            date_debut_rattrapage = session_normale.date_fin + timedelta(days=14)
            date_fin_rattrapage = date_debut_rattrapage + timedelta(days=14)
            
            self.stdout.write(f"  Session Rattrapage:")
            self.stdout.write(f"    Ancienne: {session_rattrapage.date_debut} → {session_rattrapage.date_fin}")
            self.stdout.write(f"    Nouvelle: {date_debut_rattrapage} → {date_fin_rattrapage}")
            
            if not dry_run:
                session_rattrapage.date_debut = date_debut_rattrapage
                session_rattrapage.date_fin = date_fin_rattrapage
                session_rattrapage.nom = f'Session Rattrapage {date_debut_rattrapage.year}-{date_fin_rattrapage.year}'
                session_rattrapage.save()
    
    def update_examens(self, dry_run):
        """Met à jour les dates des examens existants"""
        self.stdout.write("\n📝 Mise à jour des dates d'examens existants...")
        
        # Récupérer tous les examens
        examens = Examen.objects.all().order_by('date', 'heure_debut')
        
        if not examens.exists():
            self.stdout.write(self.style.WARNING("⚠️  Aucun examen trouvé dans la base de données"))
            return
        
        self.stdout.write(f"  Nombre d'examens à mettre à jour: {examens.count()}")
        
        # Dates d'examen (commencent le 12/12/2025)
        date_courante = self.DATE_DEBUT_EXAMENS
        jours_examens = 0
        max_jours_examens = 21  # 3 semaines
        
        # Heures d'examen possibles (4 créneaux par jour)
        creneaux_horaires = [
            (time(8, 0), time(10, 0)),   # 8h-10h
            (time(10, 30), time(12, 30)), # 10h30-12h30
            (time(14, 0), time(16, 0)),   # 14h-16h
            (time(16, 30), time(18, 30)), # 16h30-18h30
        ]
        
        # Organiser les examens par date originale
        examens_par_date = {}
        for examen in examens:
            if examen.date not in examens_par_date:
                examens_par_date[examen.date] = []
            examens_par_date[examen.date].append(examen)
        
        updated_count = 0
        
        # Parcourir les dates originales
        for date_originale, examens_du_jour in sorted(examens_par_date.items()):
            # S'assurer qu'on ne dépasse pas la période d'examen
            if jours_examens >= max_jours_examens:
                self.stdout.write(self.style.WARNING(f"  ⚠️  Limite de {max_jours_examens} jours atteinte"))
                break
            
            # Mettre à jour chaque examen de cette journée
            for i, examen in enumerate(examens_du_jour):
                try:
                    # Choisir un créneau horaire (4 créneaux par jour)
                    creneau_index = i % len(creneaux_horaires)
                    heure_debut, heure_fin = creneaux_horaires[creneau_index]
                    
                    # Si on dépasse 4 examens par jour, passer au jour suivant pour les créneaux suivants
                    if i >= len(creneaux_horaires):
                        date_examen = date_courante + timedelta(days=i // len(creneaux_horaires))
                    else:
                        date_examen = date_courante
                    
                    # Vérifier si on est samedi ou dimanche
                    while date_examen.weekday() >= 5:  # 5 = Samedi, 6 = Dimanche
                        date_examen += timedelta(days=1)
                    
                    self.stdout.write(f"  {examen.ue.code}:")
                    self.stdout.write(f"    Ancienne date: {examen.date} {examen.heure_debut}-{examen.heure_fin}")
                    self.stdout.write(f"    Nouvelle date: {date_examen.date()} {heure_debut}-{heure_fin}")
                    
                    if not dry_run:
                        examen.date = date_examen.date()
                        examen.heure_debut = heure_debut
                        examen.heure_fin = heure_fin
                        examen.save()
                    
                    updated_count += 1
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la mise à jour de l'examen {examen.id}: {e}"))
            
            # Passer au jour suivant pour le prochain groupe d'examens
            # On avance d'un jour après avoir traité tous les examens d'une date originale
            date_courante += timedelta(days=1)
            # Sauter les weekends
            while date_courante.weekday() >= 5:
                date_courante += timedelta(days=1)
            jours_examens += 1
        
        self.stdout.write(self.style.SUCCESS(f"  ✓ Examens mis à jour: {updated_count}/{examens.count()}"))
    
    def recreate_examens(self, dry_run):
        """Supprime et recrée tous les examens avec les nouvelles dates"""
        self.stdout.write("\n🔄 Recréation de tous les examens...")
        
        # Récupérer la session normale
        session_normale = SessionExamen.objects.filter(type_session='normale').first()
        if not session_normale:
            self.stdout.write(self.style.ERROR("❌ Session normale non trouvée"))
            return
        
        # Supprimer tous les examens existants
        examens_count = Examen.objects.count()
        if not dry_run and examens_count > 0:
            self.stdout.write(f"  Suppression de {examens_count} examens existants...")
            Examen.objects.all().delete()
        
        # Récupérer toutes les UEs
        ues = UE.objects.all()
        self.stdout.write(f"  Nombre d'UEs à programmer: {ues.count()}")
        
        if ues.count() == 0:
            self.stdout.write(self.style.WARNING("⚠️  Aucune UE trouvée"))
            return
        
        # Organiser les UEs par filière, niveau et semestre
        ues_par_filiere_niveau = {}
        for ue in ues:
            key = (ue.filiere.id, ue.niveau.id, ue.semestre)
            if key not in ues_par_filiere_niveau:
                ues_par_filiere_niveau[key] = []
            ues_par_filiere_niveau[key].append(ue)
        
        # Dates d'examen (commencent le 12/12/2025)
        date_courante = self.DATE_DEBUT_EXAMENS
        jours_examens = 0
        max_jours_examens = 21  # 3 semaines
        
        # Heures d'examen possibles (4 créneaux par jour)
        creneaux_horaires = [
            (time(8, 0), time(10, 0)),   # 8h-10h
            (time(10, 30), time(12, 30)), # 10h30-12h30
            (time(14, 0), time(16, 0)),   # 14h-16h
            (time(16, 30), time(18, 30)), # 16h30-18h30
        ]
        
        # Récupérer des salles (au moins 30 devraient exister)
        from core.models import Salle
        salles = list(Salle.objects.all())
        if not salles:
            self.stdout.write(self.style.WARNING("⚠️  Aucune salle trouvée, création de salles par défaut..."))
            salles = self.create_salles_par_defaut()
        
        # Récupérer un surveillant
        from django.contrib.auth.models import User
        surveillant = User.objects.filter(username='surv1').first()
        
        created_count = 0
        
        # Créer des examens pour chaque groupe d'UEs
        for (filiere_id, niveau_id, semestre), ues_groupe in ues_par_filiere_niveau.items():
            # S'assurer qu'on ne dépasse pas la période d'examen
            if jours_examens >= max_jours_examens:
                self.stdout.write(self.style.WARNING(f"  ⚠️  Limite de {max_jours_examens} jours atteinte"))
                break
            
            # Vérifier si c'est un jour ouvrable
            while date_courante.weekday() >= 5:  # 5 = Samedi, 6 = Dimanche
                date_courante += timedelta(days=1)
            
            # Pour chaque UE dans le groupe
            for i, ue in enumerate(ues_groupe):
                try:
                    # Choisir un créneau horaire
                    creneau_index = i % len(creneaux_horaires)
                    heure_debut, heure_fin = creneaux_horaires[creneau_index]
                    
                    # Choisir une salle aléatoire
                    salle = random.choice(salles) if salles else None
                    
                    # Choisir une session (normale pour la plupart, rattrapage pour quelques-uns)
                    session = session_normale
                    type_examen = 'normal'
                    
                    self.stdout.write(f"  {ue.code}:")
                    self.stdout.write(f"    Date: {date_courante.date()} {heure_debut}-{heure_fin}")
                    self.stdout.write(f"    Salle: {salle.code if salle else 'Non assignée'}")
                    
                    if not dry_run:
                        examen = Examen.objects.create(
                            ue=ue,
                            annee_academique=session.annee_academique,
                            session=session,
                            date=date_courante.date(),
                            heure_debut=heure_debut,
                            heure_fin=heure_fin,
                            type_examen=type_examen,
                            salle=salle,
                            surveillant=surveillant
                        )
                        created_count += 1
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la création de l'examen pour {ue.code}: {e}"))
            
            # Passer au jour suivant après avoir programmé toutes les UEs d'un groupe
            date_courante += timedelta(days=1)
            jours_examens += 1
        
        self.stdout.write(self.style.SUCCESS(f"  ✓ Examens créés: {created_count}"))
    
    def create_salles_par_defaut(self):
        """Crée des salles par défaut si aucune n'existe"""
        from core.models import Salle
        salles = []
        batiments = ['BAT_A', 'BAT_B', 'BAT_C']
        
        for i in range(1, 31):
            salle_data = {
                'code': f'SALLE_{i:02d}',
                'capacite': random.randint(30, 120),
                'batiment': random.choice(batiments),
                'etage': 'RDC' if i % 3 == 0 else '1ER' if i % 3 == 1 else '2EME'
            }
            salle, _ = Salle.objects.get_or_create(
                code=salle_data['code'],
                defaults=salle_data
            )
            salles.append(salle)
        
        return salles
    
    def print_summary(self):
        """Affiche un résumé des examens"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('📊 RÉSUMÉ DES EXAMENS')
        self.stdout.write('=' * 60)
        
        # Compter les examens
        total_examens = Examen.objects.count()
        self.stdout.write(f"📝 Total examens: {total_examens}")
        
        if total_examens > 0:
            # Premier et dernier examen
            premier_examen = Examen.objects.order_by('date', 'heure_debut').first()
            dernier_examen = Examen.objects.order_by('-date', '-heure_fin').first()
            
            if premier_examen and dernier_examen:
                self.stdout.write(f"📅 Période d'examens: {premier_examen.date} → {dernier_examen.date}")
                
                # Détails des 12 et 13 décembre
                self.stdout.write("\n📅 EXAMENS DES 12 ET 13 DÉCEMBRE 2025:")
                
                # 12 décembre
                examens_12 = Examen.objects.filter(date=datetime(2025, 12, 12).date())
                self.stdout.write(f"\n  📍 12 décembre 2025 ({examens_12.count()} examen(s)):")
                for examen in examens_12.order_by('heure_debut'):
                    salle_info = f"({examen.salle.code})" if examen.salle else ""
                    self.stdout.write(f"    - {examen.ue.code}: {examen.heure_debut}-{examen.heure_fin} {salle_info}")
                
                # 13 décembre
                examens_13 = Examen.objects.filter(date=datetime(2025, 12, 13).date())
                self.stdout.write(f"\n  📍 13 décembre 2025 ({examens_13.count()} examen(s)):")
                for examen in examens_13.order_by('heure_debut'):
                    salle_info = f"({examen.salle.code})" if examen.salle else ""
                    self.stdout.write(f"    - {examen.ue.code}: {examen.heure_debut}-{examen.heure_fin} {salle_info}")
                
                # Examens par date
                self.stdout.write("\n📅 CALENDRIER DES 10 PREMIERS JOURS:")
                examens_par_date = {}
                for examen in Examen.objects.all():
                    if examen.date not in examens_par_date:
                        examens_par_date[examen.date] = []
                    examens_par_date[examen.date].append(examen)
                
                dates_triees = sorted(examens_par_date.keys())
                for date in dates_triees[:10]:  # Afficher les 10 premières dates
                    examens_du_jour = examens_par_date[date]
                    jour_semaine = date.strftime('%A')
                    self.stdout.write(f"  {date} ({jour_semaine}): {len(examens_du_jour)} examen(s)")
                
                if len(dates_triees) > 10:
                    self.stdout.write(f"  ... et {len(dates_triees) - 10} autre(s) jour(s)")
                
                # Répartition par session
                self.stdout.write("\n📋 RÉPARTITION PAR SESSION:")
                examens_normaux = Examen.objects.filter(type_examen='normal').count()
                examens_rattrapage = Examen.objects.filter(type_examen='rattrapage').count()
                self.stdout.write(f"  - Session normale: {examens_normaux}")
                self.stdout.write(f"  - Session rattrapage: {examens_rattrapage}")
        
        # Sessions d'examen
        self.stdout.write("\n📋 SESSIONS D'EXAMEN:")
        sessions = SessionExamen.objects.all()
        for session in sessions:
            status = "✅ ACTIVE" if session.active else "⏸️  INACTIVE"
            self.stdout.write(f"  - {session.nom}: {session.date_debut} → {session.date_fin} ({status})")
        
        self.stdout.write('=' * 60)
        self.stdout.write('\n🎉 Les dates d\'examens ont été mises à jour avec succès!')