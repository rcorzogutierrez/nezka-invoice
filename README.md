# Nezka Invoice

Aplicación de escritorio de **Elpidio Jr. Produce Co.** para gestionar los clientes a los que se emiten proformas y facturas.

Hecha en Python con [PySide6](https://doc.qt.io/qtforpython-6/) (Qt) para la interfaz y SQLite para guardar los datos en un archivo local, sin servidor. Funciona en Windows, macOS y Linux.

![Lista de clientes](docs/clientes.png)

## Qué hace

- **Crear clientes** con nombre, sucursal o razón social, contacto, correo, teléfonos, dirección, Tax ID y notas.
- **Mantener los existentes**: editar (doble clic o botón *Editar*), marcar como inactivo o eliminar.
- **Buscar** por nombre, contacto, correo, teléfono, ciudad o Tax ID, y ordenar por cualquier columna.
- Avisa si el nombre ya existe y valida el formato del correo.

Atajos: `Ctrl+N` nuevo cliente, `Ctrl+F` buscar, `Supr` eliminar el seleccionado.

![Formulario de cliente](docs/cliente-form.png)

## Instalar y ejecutar

Requiere Python 3.10 o superior.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m nezka_invoice
```

## Dónde se guardan los datos

En un archivo `nezka.db` dentro de la carpeta de datos del usuario:

| Sistema | Ruta |
|---|---|
| Windows | `%APPDATA%\Elpidio Jr. Produce Co\Nezka Invoice\nezka.db` |
| macOS | `~/Library/Application Support/Elpidio Jr. Produce Co/Nezka Invoice/nezka.db` |
| Linux | `~/.local/share/Elpidio Jr. Produce Co/Nezka Invoice/nezka.db` |

Para respaldar los clientes basta copiar ese archivo. La variable de entorno `NEZKA_DB` permite usar otra ruta.

## Generar un ejecutable para el cliente

```bash
pip install pyinstaller
pyinstaller --name "Nezka Invoice" --windowed --onefile -p . nezka_invoice/__main__.py
```

El ejecutable queda en `dist/`. Hay que generarlo en el mismo sistema operativo donde se va a usar (un `.exe` se genera en Windows).

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```
