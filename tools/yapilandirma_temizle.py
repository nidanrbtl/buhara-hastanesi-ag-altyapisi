"""
Packet Tracer'dan dışa aktarılan running-config dosyalarını depoya konabilecek hale getirir.

Yaptığı tek iş: parola özetlerini (enable secret, username ... secret, password 7 ...)
DEGISTIR_ ile başlayan yer tutucularla değiştirmek ve satır sonlarını düzeltmek.
Yapılandırmanın geri kalanına dokunmaz; böylece configs/v3 altındaki dosyalar
cihazdan çıkan metinle aynı kalır ve tools/acl_check_v3.py gerçek kuralları okur.

Kullanım:
    python tools/yapilandirma_temizle.py <kaynak_klasör> <önek> configs/v3
    (örnek: kaynak klasörde p4-CORE1.txt varsa önek "p4-" olur, çıktı configs/v3/CORE1.cfg)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DEVICES = ["CORE1", "CORE2", "ACC-KAT1", "ACC-KAT2", "ACC-SRV", "EDGE", "ISP"]

RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(enable secret) .*$"), r"\1 DEGISTIR_ENABLE_PAROLASI"),
    (re.compile(r"^(enable password) .*$"), r"\1 DEGISTIR_ENABLE_PAROLASI"),
    (re.compile(r"^(username \S+ (?:privilege \d+ )?secret) .*$"), r"\1 DEGISTIR_SSH_PAROLASI"),
    (re.compile(r"^(username \S+ (?:privilege \d+ )?password) .*$"), r"\1 DEGISTIR_SSH_PAROLASI"),
    (re.compile(r"^( password) .*$"), r"\1 DEGISTIR_HAT_PAROLASI"),
]

# Temizlikten sonra dosyada kalmaması gereken kalıplar (özet ya da açık parola izi).
LEFTOVER = re.compile(r"secret [0-9] |password [0-9] |\$1\$")


def clean(text: str) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.rstrip()
        for pattern, replacement in RULES:
            line = pattern.sub(replacement, line)
        lines.append(line)
    return "\n".join(lines).strip("\n") + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3:
        print(__doc__)
        return 2
    source, prefix, target = Path(args[0]), args[1], Path(args[2])
    target.mkdir(parents=True, exist_ok=True)
    status = 0
    for name in DEVICES:
        path = source / f"{prefix}{name}.txt"
        if not path.exists():
            print(f"EKSIK  {path}")
            status = 1
            continue
        cleaned = clean(path.read_text(encoding="utf-8", errors="replace"))
        if LEFTOVER.search(cleaned):
            print(f"HATA   {name}: temizlikten sonra parola izi kaldı, dosya yazılmadı")
            status = 1
            continue
        (target / f"{name}.cfg").write_text(cleaned, encoding="utf-8")
        print(f"TAMAM  {name}.cfg ({len(cleaned.splitlines())} satır)")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
