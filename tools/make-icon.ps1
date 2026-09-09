Add-Type -AssemblyName System.Drawing
$bmp = New-Object Drawing.Bitmap 256,256
$g = [Drawing.Graphics]::FromImage($bmp)
$g.Clear([Drawing.Color]::FromArgb(36,103,92))
$g.SmoothingMode = 'AntiAlias'
$pen = New-Object Drawing.Pen ([Drawing.Color]::FromArgb(242,247,237)), 12
$g.DrawLine($pen, 48,80,128,96); $g.DrawLine($pen,128,96,208,80); $g.DrawLine($pen,48,80,48,185); $g.DrawLine($pen,48,185,128,202); $g.DrawLine($pen,128,202,208,185); $g.DrawLine($pen,208,80,208,185); $g.DrawLine($pen,128,96,128,202)
$brush = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(214,232,204))
$g.FillEllipse($brush,145,125,55,55); $g.DrawEllipse($pen,145,125,55,55); $g.DrawLine($pen,190,170,222,202)
$g.Dispose(); $pen.Dispose(); $brush.Dispose()
$path = Join-Path (Split-Path $PSScriptRoot -Parent) 'tools\workbench.ico'
$buffer = New-Object IO.MemoryStream
$bmp.Save($buffer, [Drawing.Imaging.ImageFormat]::Png)
$imageBytes = $buffer.ToArray()
$stream = [IO.File]::Create($path)
$writer = New-Object IO.BinaryWriter $stream
try {
    $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]1)
    $writer.Write([byte]0); $writer.Write([byte]0); $writer.Write([byte]0); $writer.Write([byte]0)
    $writer.Write([uint16]1); $writer.Write([uint16]32)
    $writer.Write([uint32]$imageBytes.Length); $writer.Write([uint32]22)
    $writer.Write($imageBytes)
} finally { $writer.Dispose(); $buffer.Dispose(); $bmp.Dispose() }
Write-Output $path
