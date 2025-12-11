from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, time
from core.models import (
    AnneeAcademique, Filiere, Niveau, UE, Etudiant,
    Paiement, InscriptionUE, Salle, SessionExamen, Examen
)

print("\n=== INSERTION DES DONNÉES INITIALES ===\n")

# ---------------------------------------------------------
# 1. Année académique
# ---------------------------------------------------------
annees = [
    "2020-2021", "2021-2022", "2022-2023",
    "2023-2024", "2024-2025"
]

annee_objects = []
for code in annees:
    obj, _ = AnneeAcademique.objects.get_or_create(code=code)
    annee_objects.append(obj)

annee_active = annee_objects[-1]  # 2024-2025


# ---------------------------------------------------------
# 2. Filières
# ---------------------------------------------------------
filieres_data = [
    ("IG", "Informatique de Gestion"),
    ("SR", "Systèmes et Réseaux"),
    ("GL", "Génie Logiciel"),
    ("TI", "Télécommunications"),
    ("IA", "Intelligence Artificielle"),
]

filieres = {}
for code, nom in filieres_data:
    f, _ = Filiere.objects.get_or_create(code=code, nom=nom)
    filieres[code] = f


# ---------------------------------------------------------
# 3. Niveaux
# ---------------------------------------------------------
niveaux_data = [
    ("L1", 1),
    ("L2", 2),
    ("L3", 3),
    ("M1", 4),
    ("M2", 5),
]

niveaux = {}
for nom, ordre in niveaux_data:
    n, _ = Niveau.objects.get_or_create(nom=nom, ordre=ordre)
    niveaux[nom] = n


# ---------------------------------------------------------
# 4. UEs
# ---------------------------------------------------------
ue_data = [
    ("IG101", "Algorithmique 1", "IG", "L1", 1),
    ("IG102", "Programmation 1", "IG", "L1", 1),
    ("SR201", "Réseaux 1", "SR", "L2", 1),
    ("GL301", "Conception Logicielle", "GL", "L3", 1),
    ("IA501", "Machine Learning", "IA", "M1", 1),
]

ues = []
for code, titre, fil, niv, sem in ue_data:
    ue, _ = UE.objects.get_or_create(
        code=code,
        intitule=titre,
        filiere=filieres[fil],
        niveau=niveaux[niv],
        semestre=sem,
        credit=6
    )
    ues.append(ue)


# ---------------------------------------------------------
# 5. Étudiants
# ---------------------------------------------------------
etudiants_data = [
    ("IG2024-001", "Ngono", "Steve", "IG", "L1"),
    ("IG2024-002", "Tchami", "Alice", "IG", "L1"),
    ("SR2024-003", "Mbarga", "Kevin", "SR", "L2"),
    ("GL2024-004", "Ndongo", "Sarah", "GL", "L3"),
    ("IA2024-005", "Kouam", "Junior", "IA", "M1"),
]

etudiants = []
for matricule, nom, prenom, fil, niv in etudiants_data:
    e, _ = Etudiant.objects.get_or_create(
        matricule=matricule,
        nom=nom,
        prenom=prenom,
        email=f"{prenom.lower()}.{nom.lower()}@gmail.com",
        telephone="+237690000000",
        date_naissance="2000-01-01",
        statut="actif",
        filiere=filieres[fil],
        niveau=niveaux[niv],
    )
    etudiants.append(e)


# ---------------------------------------------------------
# 6. Paiements
# ---------------------------------------------------------
admin, _ = User.objects.get_or_create(username="admin_test")

paiements = []
for e in etudiants:
    p, _ = Paiement.objects.get_or_create(
        etudiant=e,
        annee_academique=annee_active,
        montant=50000,
        montant_attendu=50000,
        est_regle=True,
        date_paiement=timezone.now(),
        created_by=admin,
    )
    paiements.append(p)


# ---------------------------------------------------------
# 7. Inscriptions UE
# ---------------------------------------------------------
inscriptions = []
for e, ue in zip(etudiants, ues):
    ins, _ = InscriptionUE.objects.get_or_create(
        etudiant=e,
        ue=ue,
        annee_academique=annee_active,
        est_autorise_examen=True,
        created_by=admin
    )
    inscriptions.append(ins)


# ---------------------------------------------------------
# 8. Salles
# ---------------------------------------------------------
salles_data = [
    ("S101", 40, "A", "1"),
    ("S102", 50, "A", "1"),
    ("S201", 60, "B", "2"),
    ("LAB1", 30, "C", "0"),
    ("AMPHI1", 200, "D", "0"),
]

salles = []
for code, cap, bat, etg in salles_data:
    s, _ = Salle.objects.get_or_create(
        code=code, capacite=cap, batiment=bat, etage=etg
    )
    salles.append(s)


# ---------------------------------------------------------
# 9. Sessions d'examen
# ---------------------------------------------------------
sessions_data = [
    ("Session Normale 2024", "normale", "2024-06-01", "2024-06-15"),
    ("Rattrapage 2024", "rattrapage", "2024-08-01", "2024-08-10"),
]

sessions = []
for nom, typ, d1, d2 in sessions_data:
    sess, _ = SessionExamen.objects.get_or_create(
        nom=nom,
        type_session=typ,
        annee_academique=annee_active,
        date_debut=d1,
        date_fin=d2,
        active=True,
        created_by=admin
    )
    sessions.append(sess)


# ---------------------------------------------------------
# 10. Examens
# ---------------------------------------------------------
from datetime import date, time

examens_data = [
    (ues[0], date(2024, 6, 2),  time(8, 0),  time(10, 0), salles[0], sessions[0]),
    (ues[1], date(2024, 6, 3),  time(10, 0), time(12, 0), salles[1], sessions[0]),
    (ues[2], date(2024, 6, 4),  time(8, 0),  time(11, 0), salles[2], sessions[0]),
    (ues[3], date(2024, 6, 5),  time(9, 0),  time(12, 0), salles[3], sessions[0]),
    (ues[4], date(2024, 6, 6),  time(14, 0), time(17, 0), salles[4], sessions[0]),
]

for ue, d, hd, hf, salle, sess in examens_data:
    Examen.objects.get_or_create(
    ue=ue,
    annee_academique=annee_active,
    session=sess,
    date=d,  # maintenant c'est un objet date(), pas une string
    heure_debut=hd,
    heure_fin=hf,
    salle=salle,
    surveillant=admin,
    created_by=admin
)


print("→ ✔ Données insérées avec succès !")
