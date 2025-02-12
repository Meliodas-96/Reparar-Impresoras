# Administrador de Impresoras

Este script de PowerShell proporciona una interfaz gráfica para gestionar impresoras en un sistema Windows. Permite cargar, agregar y borrar impresoras tanto de la configuración de Windows como del registro del sistema.

## Funcionalidades

- **Cargar Impresoras**: Muestra una lista de todas las impresoras instaladas en el sistema.
- **Borrar Impresora**: Permite seleccionar una impresora de la lista y eliminarla tanto de la configuración de Windows como del registro.
- **Agregar Impresora**: Permite agregar una nueva impresora al registro del sistema.

## Requisitos

- Windows PowerShell
- Permisos de administrador para modificar el registro del sistema y la configuración de impresoras.

## Instrucciones de Uso

1. **Ejecutar el Script**: Abra el .exe con privilegios de administrador y ejecute la aplicacion `Borrar_Impresoras_Regedit.exe`.
   
2. **Cargar Impresoras**: Haga clic en el botón "Cargar Impresoras" para ver la lista de impresoras instaladas.

3. **Borrar una Impresora**:
   - Seleccione una impresora de la lista.
   - Haga clic en "Borrar Impresora".
   - Confirme la eliminación cuando se le solicite.

4. **Agregar una Impresora**:
   - Haga clic en "Agregar Impresora".
   - Ingrese el nombre de la nueva impresora en el cuadro de diálogo.
   - Haga clic en "OK" para agregar la impresora.

## Advertencias

- **Modificación del Registro**: Este script modifica el registro de Windows. Asegúrese de tener una copia de seguridad antes de realizar cambios.
- **Permisos**: Se requieren permisos de administrador para ejecutar este script correctamente.

## Notas

- Este script está diseñado para ser utilizado en entornos Windows y puede no funcionar correctamente en otros sistemas operativos.
- Asegúrese de tener los controladores de impresora necesarios instalados antes de agregar una nueva impresora.

## Contacto

Para más información o soporte, por favor contacte al desarrollador del script.