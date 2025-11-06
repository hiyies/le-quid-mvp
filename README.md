
# le quid — MVP (prototype de test)
Plateforme minimaliste pour publier des **prologues** (sujets) et des **répliques** (réponses). Aucune identification. Inclut un formulaire "l’idée vous intéresse ?" pour collecter des e-mails.

## ⚙️ lancer en local
```bash
python -m venv .venv
source .venv/bin/activate  # sous Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
# ouvrir http://127.0.0.1:5000
```

## 📦 déployer rapidement (gratuit)
- **Render** (recommandé) : créer un "Web Service", Python, connecter votre repo, définir `start command: gunicorn app:app`
- **Railway** : nouveau projet → déployer à partir d'un repo → `gunicorn app:app`
- **Fly.io** : `fly launch` (option avancée)

## 🧱 fonctionnalités
- créer des prologues (+ catégorie optionnelle)
- publier des répliques
- liste par catégorie
- collecte d’e-mails d’intérêt

## 🔮 évolutions possibles (v2)
- votes `./↑` et `./↓`
- rôles `disciple / érudite / élite`
- modération et balises (`cf.`, `réf.`, `a.i.`, `cqfd.`, `à.n.`)
- authentification légère (supabase / firebase / auth simple)

## 📝 licence
Usage libre pour test. Crédits: projet *le quid*.
