"""
build_pe.py - Generador de metadatos PE (Resource Script & Manifest) y compilador seguro para C en Windows.

Este script ayuda a desarrolladores a incorporar todos los metadatos necesarios
(información de versión, manifiesto de compatibilidad UAC/SO, flags de seguridad ASLR/DEP)
en binarios compilados en C para reducir falsos positivos causados por motores heurísticos.
"""

import os
import sys
import argparse
import subprocess
import shutil

MANIFEST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity
    version="{version_str}"
    processorArchitecture="*"
    name="{company_clean}.{product_clean}"
    type="win32"
  />
  <description>{description}</description>

  <!-- Nivel de permisos UAC requerido -->
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v2">
    <security>
      <requestedPrivileges xmlns="urn:schemas-microsoft-com:asm.v3">
        <requestedExecutionLevel level="asInvoker" uiAccess="false" />
      </requestedPrivileges>
    </security>
  </trustInfo>

  <!-- Declaración de compatibilidad con versiones de Windows modernas -->
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows 10 y Windows 11 -->
      <supportedOS Id="{{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}}" />
      <!-- Windows 8.1 -->
      <supportedOS Id="{{1f676c76-80e1-4239-95bb-83d0f6d0da78}}" />
      <!-- Windows 8 -->
      <supportedOS Id="{{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}}" />
      <!-- Windows 7 -->
      <supportedOS Id="{{35138b9a-5d96-4fbd-8e2d-a2440225f93a}}" />
    </application>
  </compatibility>
</assembly>
"""

RC_TEMPLATE = """#include <windows.h>

// Definición de ID del manifiesto si no se incluye por linker
1 RT_MANIFEST "{manifest_file}"

{icon_definition}

VS_VERSION_INFO VERSIONINFO
FILEVERSION     {version_comma}
PRODUCTVERSION  {version_comma}
FILEFLAGSMASK   VS_FFI_FILEFLAGSMASK
FILEFLAGS       0x0L
FILEOS          VOS_NT_WINDOWS32
FILETYPE        VFT_APP
FILESUBTYPE     VFT2_UNKNOWN
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        // 040904B0 = Idioma: Inglés (EE.UU.), Codificación: Unicode
        BLOCK "040904B0"
        BEGIN
            VALUE "CompanyName",      "{company}\\0"
            VALUE "FileDescription",  "{description}\\0"
            VALUE "FileVersion",      "{version_str}\\0"
            VALUE "InternalName",     "{product_clean}\\0"
            VALUE "LegalCopyright",   "{copyright}\\0"
            VALUE "OriginalFilename", "{output_exe}\\0"
            VALUE "ProductName",      "{product}\\0"
            VALUE "ProductVersion",   "{version_str}\\0"
        END
    END

    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1200
    END
END
"""

def parse_version(ver_str):
    parts = ver_str.split('.')
    while len(parts) < 4:
        parts.append('0')
    parts = parts[:4]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        nums = [1, 0, 0, 0]
    return f"{nums[0]},{nums[1]},{nums[2]},{nums[3]}", f"{nums[0]}.{nums[1]}.{nums[2]}.{nums[3]}"

def generate_manifest(output_dir, config):
    manifest_path = os.path.join(output_dir, "app.manifest")
    content = MANIFEST_TEMPLATE.format(
        version_str=config["version_str"],
        company_clean=config["company"].replace(" ", ""),
        product_clean=config["product"].replace(" ", ""),
        description=config["description"]
    )
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"[+] Manifiesto generado: {manifest_path}")
    return "app.manifest"

def generate_rc(output_dir, config, manifest_filename):
    rc_path = os.path.join(output_dir, "version.rc")
    icon_def = ""
    if config.get("icon") and os.path.exists(config["icon"]):
        icon_path_escaped = config["icon"].replace("\\", "\\\\")
        icon_def = f'1 ICON "{icon_path_escaped}"'

    content = RC_TEMPLATE.format(
        manifest_file=manifest_filename.replace("\\", "\\\\"),
        icon_definition=icon_def,
        version_comma=config["version_comma"],
        version_str=config["version_str"],
        company=config["company"],
        description=config["description"],
        product_clean=config["product"].replace(" ", ""),
        copyright=config["copyright"],
        output_exe=config["output_exe"],
        product=config["product"]
    )
    with open(rc_path, "w", encoding="utf-8") as f:
        f.write(content.strip())
    print(f"[+] Archivo de recursos generado: {rc_path}")
    return rc_path

def compile_project(c_source, rc_path, output_exe, compiler=None):
    """
    Intenta compilar utilizando MinGW (gcc/windres) o MSVC (cl/rc).
    Incluye banderas de mitigación de seguridad esenciales: ASLR, DEP / NX y High Entropy VA.
    """
    # Detectar compilador si no se especificó
    if not compiler:
        if shutil.which("gcc") and shutil.which("windres"):
            compiler = "gcc"
        elif shutil.which("cl") and shutil.which("rc"):
            compiler = "msvc"
        else:
            print("\n[!] No se encontró ni GCC (MinGW) ni MSVC (cl) en el PATH del sistema.")
            print("[i] Los archivos de recursos fueron generados exitosamente.")
            print("[i] Para compilar manualmente con MinGW:")
            print(f"    windres {rc_path} -O coff -o version.res")
            print(f"    gcc {c_source} version.res -o {output_exe} -Wl,--dynamicbase -Wl,--nxcompat -Wl,--high-entropy-va -s -O2\n")
            return False

    workdir = os.path.dirname(os.path.abspath(rc_path))

    if compiler == "gcc":
        print("[*] Compilando con GCC / MinGW...")
        res_file = os.path.join(workdir, "version.res")
        
        # 1. Compilar recursos
        cmd_rc = ["windres", rc_path, "-O", "coff", "-o", res_file]
        print("    Ejecutando:", " ".join(cmd_rc))
        res = subprocess.run(cmd_rc, cwd=workdir)
        if res.returncode != 0:
            print("[-] Error compilando el archivo de recursos con windres.")
            return False

        # 2. Compilar ejecutable con mitigaciones de seguridad modernas
        cmd_gcc = [
            "gcc", c_source, res_file, "-o", output_exe,
            "-O2",                         # Optimización estándar
            "-s",                          # Strip debug symbols estándar
            "-fstack-protector-strong",    # Protección de stack
            "-Wl,--dynamicbase",           # Habilitar ASLR
            "-Wl,--nxcompat",              # Habilitar DEP (Data Execution Prevention)
            "-Wl,--high-entropy-va"        # ASLR de 64 bits de alta entropía
        ]
        print("    Ejecutando:", " ".join(cmd_gcc))
        res = subprocess.run(cmd_gcc, cwd=workdir)
        if res.returncode == 0:
            print(f"\n[+] Compilación completada con éxito: {output_exe}")
            return True
        else:
            print("[-] Error compilando el código C con gcc.")
            return False

    elif compiler == "msvc":
        print("[*] Compilando con MSVC (cl.exe)...")
        res_file = os.path.join(workdir, "version.res")
        
        cmd_rc = ["rc.exe", f"/fo{res_file}", rc_path]
        print("    Ejecutando:", " ".join(cmd_rc))
        res = subprocess.run(cmd_rc, cwd=workdir)
        if res.returncode != 0:
            print("[-] Error compilando recursos con rc.exe.")
            return False

        cmd_cl = [
            "cl.exe", c_source, res_file,
            f"/Fe:{output_exe}",
            "/O2", "/GS",                  # Buffer security check
            "/link",
            "/DYNAMICBASE",                # ASLR
            "/NXCOMPAT",                   # DEP
            "/HIGHENTROPYVA"               # 64-bit ASLR
        ]
        print("    Ejecutando:", " ".join(cmd_cl))
        res = subprocess.run(cmd_cl, cwd=workdir)
        if res.returncode == 0:
            print(f"\n[+] Compilación completada con éxito: {output_exe}")
            return True
        else:
            print("[-] Error compilando con cl.exe.")
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Genera metadatos PE completos y compila C de forma segura en Windows."
    )
    parser.add_argument("--source", "-s", default="main.c", help="Archivo fuente .c (por defecto: main.c)")
    parser.add_argument("--output", "-o", default="app.exe", help="Nombre del ejecutable final (por defecto: app.exe)")
    parser.add_argument("--company", default="MyCompany Ltd.", help="Nombre de la empresa u organización")
    parser.add_argument("--product", default="MyApp", help="Nombre del producto/software")
    parser.add_argument("--description", default="Aplicación de utilidad para Windows", help="Descripción del archivo")
    parser.add_argument("--version", default="1.0.0.0", help="Versión (ej. 1.0.0.0)")
    parser.add_argument("--copyright", default="Copyright (C) 2026. Todos los derechos reservados.", help="Texto de Copyright")
    parser.add_argument("--icon", default="", help="Ruta a un archivo de icono .ico (opcional)")
    parser.add_argument("--compile", "-c", action="store_true", help="Intentar compilar automáticamente el binario")

    args = parser.parse_args()

    v_comma, v_str = parse_version(args.version)
    config = {
        "company": args.company,
        "product": args.product,
        "description": args.description,
        "version_comma": v_comma,
        "version_str": v_str,
        "copyright": args.copyright,
        "output_exe": args.output,
        "icon": args.icon
    }

    output_dir = os.path.dirname(os.path.abspath(args.source)) if os.path.exists(args.source) else os.getcwd()

    print("=====================================================")
    print("      CONFIGURADOR DE METADATOS PE PARA WINDOWS      ")
    print("=====================================================")
    print(f"[*] Producto:    {config['product']}")
    print(f"[*] Compañía:    {config['company']}")
    print(f"[*] Versión:     {config['version_str']}")
    print(f"[*] Descripción: {config['description']}")
    print(f"[*] Ejecutable:  {config['output_exe']}")
    print("-----------------------------------------------------")

    # 1. Generar Manifiesto
    manifest_name = generate_manifest(output_dir, config)

    # 2. Generar Archivo de Recursos (.rc)
    rc_path = generate_rc(output_dir, config, manifest_name)

    # 3. Compilación si se solicita
    if args.compile:
        if not os.path.exists(args.source):
            print(f"\n[-] No se encontró el archivo fuente '{args.source}'. No se puede compilar.")
            sys.exit(1)
        compile_project(args.source, rc_path, args.output)
    else:
        print("\n[i] Archivos de recursos listos.")
        print("[i] Para compilar junto a tu código C:")
        print(f"    windres version.rc -O coff -o version.res")
        print(f"    gcc {args.source} version.res -o {args.output} -Wl,--dynamicbase -Wl,--nxcompat -Wl,--high-entropy-va\n")

if __name__ == "__main__":
    main()
