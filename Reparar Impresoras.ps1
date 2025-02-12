Add-Type -AssemblyName System.Windows.Forms

# Crear el formulario principal
$form = New-Object System.Windows.Forms.Form
$form.Text = "Administrador de Impresoras"
$form.Size = New-Object System.Drawing.Size(400, 300)

# Crear una lista para mostrar las impresoras
$listBox = New-Object System.Windows.Forms.ListBox
$listBox.Location = New-Object System.Drawing.Point(10, 10)
$listBox.Size = New-Object System.Drawing.Size(360, 200)
$form.Controls.Add($listBox)

# Función para cargar las impresoras desde el registro
function Load-Printers {
    $listBox.Items.Clear()
    $printers = Get-ChildItem -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Print\Printers" | Select-Object -ExpandProperty PSChildName
    foreach ($printer in $printers) {
        $listBox.Items.Add($printer)
    }
}

# Botón para cargar las impresoras
$loadButton = New-Object System.Windows.Forms.Button
$loadButton.Location = New-Object System.Drawing.Point(10, 220)
$loadButton.Size = New-Object System.Drawing.Size(100, 35)
$loadButton.Text = "Cargar Impresoras"
$loadButton.Add_Click({ Load-Printers })
$form.Controls.Add($loadButton)

# Botón para borrar la impresora seleccionada
$deleteButton = New-Object System.Windows.Forms.Button
$deleteButton.Location = New-Object System.Drawing.Point(120, 220)
$deleteButton.Size = New-Object System.Drawing.Size(100, 35)
$deleteButton.Text = "Borrar Impresora"
$deleteButton.Add_Click({
    if ($listBox.SelectedItem) {
        $printerName = $listBox.SelectedItem

        # Confirmar la eliminación
        $confirm = [System.Windows.Forms.MessageBox]::Show(
            "¿Estás seguro de que deseas borrar la impresora '$printerName'?",
            "Confirmar Borrado",
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Warning
        )

        if ($confirm -eq [System.Windows.Forms.DialogResult]::Yes) {
            try {
                # Borrar la impresora de la configuración de Windows
                if (Get-Printer -Name $printerName -ErrorAction SilentlyContinue) {
                    Remove-Printer -Name $printerName -ErrorAction Stop
                    [System.Windows.Forms.MessageBox]::Show("Impresora '$printerName' borrada de la configuración de Windows.", "Éxito", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)
                }

                # Borrar la impresora del registro
                Remove-Item -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Print\Printers\$printerName" -Recurse -Force -ErrorAction Stop
                [System.Windows.Forms.MessageBox]::Show("Impresora '$printerName' borrada del registro.", "Éxito", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)

                # Recargar la lista de impresoras
                Load-Printers
            } catch {
                [System.Windows.Forms.MessageBox]::Show("Error al borrar la impresora: $_", "Error", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
            }
        }
    }
})
$form.Controls.Add($deleteButton)

# Botón para agregar una nueva impresora
$addButton = New-Object System.Windows.Forms.Button
$addButton.Location = New-Object System.Drawing.Point(230, 220)
$addButton.Size = New-Object System.Drawing.Size(100, 35)
$addButton.Text = "Agregar Impresora"
$addButton.Add_Click({
    $inputBox = New-Object System.Windows.Forms.Form
    $inputBox.Text = "Agregar Impresora"
    $inputBox.Size = New-Object System.Drawing.Size(300, 150)
    $inputBox.StartPosition = "CenterScreen"

    $label = New-Object System.Windows.Forms.Label
    $label.Text = "Ingrese el nombre de la nueva impresora:"
    $label.Location = New-Object System.Drawing.Point(10, 20)
    $label.Size = New-Object System.Drawing.Size(280, 20)
    $inputBox.Controls.Add($label)

    $textBox = New-Object System.Windows.Forms.TextBox
    $textBox.Location = New-Object System.Drawing.Point(10, 50)
    $textBox.Size = New-Object System.Drawing.Size(260, 20)
    $inputBox.Controls.Add($textBox)

    $okButton = New-Object System.Windows.Forms.Button
    $okButton.Location = New-Object System.Drawing.Point(75, 80)
    $okButton.Size = New-Object System.Drawing.Size(75, 23)
    $okButton.Text = "OK"
    $okButton.DialogResult = [System.Windows.Forms.DialogResult]::OK
    $inputBox.AcceptButton = $okButton
    $inputBox.Controls.Add($okButton)

    $cancelButton = New-Object System.Windows.Forms.Button
    $cancelButton.Location = New-Object System.Drawing.Point(160, 80)
    $cancelButton.Size = New-Object System.Drawing.Size(75, 23)
    $cancelButton.Text = "Cancelar"
    $cancelButton.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
    $inputBox.CancelButton = $cancelButton
    $inputBox.Controls.Add($cancelButton)

    $result = $inputBox.ShowDialog()

    if ($result -eq [System.Windows.Forms.DialogResult]::OK -and $textBox.Text) {
        $printerName = $textBox.Text
        try {
            New-Item -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Print\Printers\$printerName" -Force
            Load-Printers
        } catch {
            [System.Windows.Forms.MessageBox]::Show("Error al agregar la impresora: $_", "Error", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
        }
    }
})
$form.Controls.Add($addButton)

# Mostrar el formulario
$form.Add_Shown({ $form.Activate() })
[void]$form.ShowDialog()