# Windows PE Metadata & Build Helper

Herramienta en Python para generar recursos de Windows PE (`VERSIONINFO`, `.rc`), manifiestos de aplicación (`.manifest`), e incorporar mitigaciones de seguridad modernas (ASLR, DEP) al compilar código C en Windows. 

Diseñado para ayudar a desarrolladores a estructurar correctamente ejecutables en C y prevenir **falsos positivos** generados por motores heurísticos y de reputación (como Windows Defender y SmartScreen).

---

## 📋 ¿Por qué los binarios en C generan falsos positivos?

Los programas pequeños o recién compilados en C (especialmente mediante MinGW/GCC) suelen carecer de:
1. **Recursos de versión (`VERSIONINFO`)**: Metadatos de autor, empresa, versión, descripción y copyright.
2. **Manifiesto de aplicación (`RT_MANIFEST`)**: Declaración explícita de privilegios UAC (`asInvoker`) y versiones compatibles de Windows.
3. **Mitigaciones de memoria modernas**: Banderas como ASLR (`--dynamicbase`) y DEP/NX (`--nxcompat`).
4. **Firma digital (Authenticode)**: Confianza y reputación en Windows SmartScreen.

Este proyecto automatiza la generación de todos estos componentes antes o durante la compilación.

---

## 🚀 Requisitos

- **Python**: 3.8 o superior (sin dependencias externas).
- **Compilador C para Windows**:
  - **MinGW-w64** (`gcc` y `windres`), o
  - **MSVC / Visual Studio Build Tools** (`cl.exe` y `rc.exe`).

---

## 🛠️ Uso

### 1. Generación de recursos y manifiesto

Puedes ejecutar el script pasando los metadatos de tu software:

```powershell
python build_pe.py `
  --source "main.c" `
  --output "MiApp.exe" `
  --product "MiApp" `
  --company "MiEmpresa" `
  --version "1.0.0.0" `
  --description "Utilidad de procesamiento de datos" `
  --copyright "Copyright (C) 2026 MiEmpresa. Todos los derechos reservados."
```

#### Parámetros disponibles:

| Parámetro | Alias | Descripción | Valor por defecto |
| :--- | :--- | :--- | :--- |
| `--source` | `-s` | Archivo fuente `.c` | `main.c` |
| `--output` | `-o` | Nombre del ejecutable de salida | `app.exe` |
| `--product` | | Nombre comercial del producto | `MyApp` |
| `--company` | | Nombre del desarrollador u organización | `MyCompany Ltd.` |
| `--description`| | Descripción corta de la aplicación | Aplicación de utilidad para Windows |
| `--version` | | Versión numérica (formato `X.Y.Z.W`) | `1.0.0.0` |
| `--copyright` | | Cadena de derechos de autor | *Copyright (C)...* |
| `--icon` | | Ruta al archivo `.ico` (opcional) | Ninguno |
| `--compile` | `-c` | Compilar automáticamente si el compilador está en PATH | Desactivado |

---

## ⚙️ Proceso de Compilación Manual

El script genera `version.rc` y `app.manifest`. Para compilar manualmente junto con tu código fuente en C:

### Opción A: MinGW / GCC

```powershell
# 1. Compilar los metadatos y manifiesto a formato binario de recursos COFF
windres version.rc -O coff -o version.res

# 2. Compilar el programa en C con mitigaciones de seguridad
gcc main.c version.res -o MiApp.exe `
  -O2 `
  -s `
  -fstack-protector-strong `
  -Wl,--dynamicbase `
  -Wl,--nxcompat `
  -Wl,--high-entropy-va
```

#### Banderas de mitigación recomendadas:
- `-Wl,--dynamicbase`: Habilita ASLR (Address Space Layout Randomization).
- `-Wl,--nxcompat`: Habilita DEP (Data Execution Prevention).
- `-Wl,--high-entropy-va`: Habilita ASLR de 64 bits de alta entropía.
- `-fstack-protector-strong`: Protege contra desbordamientos de búfer en pila.
- `-s`: Elimina símbolos de depuración innecesarios.

---

### Opción B: Microsoft Visual C++ (MSVC)

```powershell
# 1. Compilar el script de recursos
rc.exe version.rc

# 2. Compilar con cl.exe habilitando mitigaciones de seguridad
cl.exe main.c version.res /Fe:MiApp.exe /O2 /GS /link /DYNAMICBASE /NXCOMPAT /HIGHENTROPYVA
```

---

## 🔍 Verificación de Metadatos

Para comprobar que Windows lee correctamente los metadatos integrados en el ejecutable, ejecuta en PowerShell:

```powershell
(Get-Item .\MiApp.exe).VersionInfo | Format-List
```

O haz clic derecho en el archivo `.exe` en el Explorador de Windows y selecciona **Propiedades > Detalles**.

---

## 🔐 Firma Digital de Código (Code Signing)

Para software destinado a distribución pública, firmar el binario con un certificado digital Authenticode es el estándar de la industria para evitar bloqueos de Windows SmartScreen:

```powershell
signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 MiApp.exe
```

### Reporte de Falsos Positivos
Si un binario legítimo aún es marcado por la heurística de Windows Defender:
1. Accede al portal oficial de [Microsoft Defender Security Intelligence - File Submission](https://www.microsoft.com/en-us/wdsi/filesubmission).
2. Selecciona **Software developer** y marca la opción **Incorrectly detected as malware (false positive)**.
3. Microsoft analiza y remueve la detección de sus definiciones habitualmente en cuestión de horas.
