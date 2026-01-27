# Marketplace de Emprendedores (Streamlit) — MVP (Light UI)

Esta versión mejora la UI:
- Tema claro (no oscuro)
- Tarjetas limpias estilo marketplace
- Sidebar sin el listado automático de pages/ (usamos `views/`)

## Instalación
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py

```


## Nota de hashing
Se usa PBKDF2-SHA256 (Passlib) para evitar fallos de bcrypt en algunos Windows/Python.
