# Marketplace de Emprendedores (Streamlit) — MVP (Light UI)

Esta versión mejora la UI:
- Tema claro (no oscuro)
- Tarjetas limpias estilo marketplace
- Sidebar sin el listado automático de pages/ (usamos `views/`)

## Instalación
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Credenciales demo (seed automático)
- ADMIN:  admin@demo.com / Admin123!
- EMP:    emprendedor@demo.com / Emprendedor123!

## Nota de hashing
Se usa PBKDF2-SHA256 (Passlib) para evitar fallos de bcrypt en algunos Windows/Python.
