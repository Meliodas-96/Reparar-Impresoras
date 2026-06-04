# Reparar-Impresoras

Administrador de impresoras para Windows con interfaz PyQt y opciones de borrado, incluida una función de eliminación completa con credenciales de administrador.

## Descripción

Esta herramienta permite listar impresoras instaladas en Windows, borrar impresoras seleccionadas y realizar un "borrado total" mediante un usuario administrador. La aplicación está construida con Python y PyQt, y usa comandos nativos de Windows para gestionar impresoras y servicios.

## Características

- Listar impresoras instaladas en el sistema.
- Buscar impresoras por nombre.
- Eliminar impresoras seleccionadas.
- Borrado total avanzado con reinicio del servicio de impresión y eliminación de registros.
- Interfaz gráfica moderna con PyQt.

## Requisitos

- Windows 10/11.
- Python 3.8+.
- PyQt5 o PyQt6.

## Instalación

1. Clona este repositorio:

```bash
git clone https://github.com/Meliodas-96/Reparar-Impresoras.git
cd Reparar-Impresoras
```

2. Crea y activa un entorno virtual:

```bash
python -m venv venv
venv\Scripts\activate
```

3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Uso

Ejecuta la aplicación con:

```bash
python main.py
```

### Notas de uso

- La función de "Borrado Total (Admin)" solicita la contraseña del usuario local `Administrador`.
- Algunas operaciones requieren permisos elevados y deben ejecutarse en un equipo Windows.

## Archivos importantes

- `main.py`: código principal de la aplicación.
- `requirements.txt`: dependencias del proyecto.
- `main.spec`: archivo de PyInstaller para generar un ejecutable.

## Cómo contribuir

1. Crea una rama para tu cambio:

```bash
git checkout -b feature/nueva-funcionalidad
```

2. Realiza tus cambios.
3. Haz commit y push:

```bash
git add .
git commit -m "Descripción de los cambios"
git push origin feature/nueva-funcionalidad
```

## Licencia

Este repositorio no incluye una licencia explícita. Agrega una licencia si deseas compartirlo públicamente bajo términos claros.
