# DMX Desk für Raspberry Pi 5

DMX Desk ist eine lokal laufende Webanwendung zur Steuerung von zwei in Reihe verbundenen RGB-DMX-Scheinwerfern. Beide Geräte lassen sich einzeln ein- und ausschalten sowie frei einfärben. Zusätzlich gibt es eine gemeinsame Farbe, Ein/Aus für beide Geräte und einen sofortigen Blackout.

Die Anwendung bindet sich an `0.0.0.0:8000` und ist damit von Handy, Tablet oder Rechner im selben Netzwerk erreichbar. Die DMX-Ausgabe läuft kontinuierlich mit 30 Hz und verwendet 250.000 Baud, 8 Datenbits, keine Parität und 2 Stopbits.

## Voraussetzungen

- Raspberry Pi 5 mit aktuellem Raspberry Pi OS (64 Bit empfohlen)
- Velleman VMA432 DMX512-Modul aus der [Herstelleranleitung](https://m.media-amazon.com/images/I/81mam8nSMHL.pdf)
- drei Female-to-Female-Jumperkabel für 5 V, GND und TX
- zwei RGB-DMX-Scheinwerfer mit 3-poligem XLR
- echte DMX-Kabel (120 Ohm), kein Mikrofonkabel
- 120-Ohm-DMX-Abschlussstecker am letzten Gerät
- separate, passende Netzversorgung für beide Scheinwerfer

> Wichtig: Den Raspberry Pi und das VMA432 vor dem Verdrahten vollständig ausschalten. Die GPIOs des Raspberry Pi arbeiten nur mit 3,3 V. Niemals 5 V auf einen GPIO legen. Der Aufbau nutzt ausschließlich den TX-Ausgang des Pi zum Eingang des VMA432; vom VMA432 führt keine Signalleitung zurück zum Pi.

Die im VMA432 verwendeten Treiber MAX485 beziehungsweise SN75176 erkennen laut ihren Datenblättern bereits mindestens 2,0 V als High-Pegel. Das 3,3-V-TX-Signal des Raspberry Pi kann ihren Eingang daher direkt treiben. Das gilt nur in dieser Richtung; ein 5-V-Ausgang darf weiterhin nie an einen Pi-GPIO angeschlossen werden.

## VMA432 am Raspberry Pi 5 anschließen

Laut VMA432-Handbuch benötigt das Modul 5 V und GND und führt das Signal am Anschluss `input` in seinen MAX-485/SN75176-Treiber. Der dreipolige XLR-Ausgang ist mit Pin 1 = Signal Common, Pin 2 = Data- und Pin 3 = Data+ belegt.

| Raspberry Pi 5, 40-Pin-Header | VMA432 | Funktion |
|---|---|---|
| physischer Pin 2 (5 V) | `+5V` | Versorgung des Moduls |
| physischer Pin 6 (GND) | `GND` | gemeinsame Signalmasse |
| physischer Pin 8 (GPIO 14 / TXD0) | `input` | serielles DMX-Datensignal |
| physischer Pin 10 (GPIO 15 / RXD0) | nicht anschließen | wird nicht benötigt |

Der VMA432 wird nur aus dem 5-V-Pin versorgt. Die Scheinwerfer dürfen **niemals** aus dem Raspberry Pi oder dem VMA432 gespeist werden.

### UART0 auf GPIO 14/15 aktivieren

Beim Raspberry Pi 5 liegt der primäre Debug-UART standardmäßig nicht am 40-Pin-Header. Deshalb UART0 explizit auf GPIO 14/15 legen:

```bash
sudo nano /boot/firmware/config.txt
```

Am Ende ergänzen:

```ini
enable_uart=1
dtoverlay=uart0-pi5
```

Danach mit `sudo raspi-config` unter **Interface Options > Serial Port** die serielle Login-Shell deaktivieren (`No`) und die UART-Hardware aktivieren (`Yes`). Anschließend neu starten:

```bash
sudo reboot
```

Nach dem Neustart prüfen:

```bash
ls -l /dev/ttyAMA0
pinctrl get 14
```

GPIO 14 muss als UART-TX konfiguriert sein. Die Anwendung verwendet standardmäßig `/dev/ttyAMA0`. Falls der UART auf deinem Image anders heißt, den tatsächlichen Gerätenamen in `/etc/default/dmx-controller` als `DMX_PORT=...` eintragen.

## DMX-Kette und Adressen

```text
Raspberry Pi 5 TX ──> VMA432 ──XLR──> DMX IN Scheinwerfer 1
                                      DMX OUT ──> DMX IN Scheinwerfer 2
                                                   DMX OUT ──> 120-Ohm-Terminator
```

Beide Scheinwerfer am Gerät in den **3-Kanal-RGB-Modus** stellen:

| Gerät | DMX-Startadresse | Kanäle |
|---|---:|---|
| Scheinwerfer 1 | 1 | 1 = Rot, 2 = Grün, 3 = Blau |
| Scheinwerfer 2 | 4 | 4 = Rot, 5 = Grün, 6 = Blau |

Die genaue Tastenfolge für Modus und Adresse steht im Handbuch des jeweiligen Scheinwerfers. `A001`, `d001` oder ähnlich bezeichnet häufig Adresse 1, ist aber herstellerabhängig.

### Abweichende Kanalbelegung

Hat ein Scheinwerfer beispielsweise Kanal 1 = Master-Dimmer und danach R/G/B, `config/fixtures.json` so anpassen:

```json
{
  "id": 1,
  "name": "Scheinwerfer links",
  "address": 1,
  "channels": { "dimmer": 0, "red": 1, "green": 2, "blue": 3 },
  "dimmer_on": 255
}
```

Die Offsets in `channels` sind nullbasiert: Offset 0 entspricht der Startadresse. Die Startadresse des zweiten Geräts muss hinter allen belegten Kanälen des ersten liegen.

## Installation auf dem Raspberry Pi

Das Projekt auf den Raspberry Pi kopieren, in den Projektordner wechseln und ausführen:

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

Nach der UART-Konfiguration und dem Neustart:

```bash
sudo systemctl start dmx-controller
sudo systemctl status dmx-controller
```

Die Oberfläche ist danach erreichbar unter:

```text
http://raspberrypi.local:8000
```

Alternativ die IP-Adresse anzeigen lassen und `http://<IP-ADRESSE>:8000` öffnen:

```bash
hostname -I
```

Der Dienst startet künftig automatisch beim Booten. Er beginnt aus Sicherheitsgründen immer mit beiden Scheinwerfern **ausgeschaltet**.

## Test ohne Hardware

Für einen UI-Test am Entwicklungsrechner:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DMX_SIMULATION=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Unter Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DMX_SIMULATION="true"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Konfiguration und Diagnose

Laufzeitwerte stehen in `/etc/default/dmx-controller`:

```ini
DMX_PORT=/dev/ttyAMA0
DMX_REFRESH_HZ=30
DMX_FIXTURES_FILE=config/fixtures.json
DMX_SIMULATION=false
```

Nach Änderungen den Dienst neu starten:

```bash
sudo systemctl restart dmx-controller
journalctl -u dmx-controller -n 50 --no-pager
```

Wenn die Weboberfläche funktioniert, aber kein Licht reagiert:

1. Stimmen 3-Kanal-Modus und Startadressen 1/4 an den Geräten?
2. Sind `Data-` und `Data+` nicht vertauscht? Beim VMA432 gilt XLR-Pin 2 = Data-, Pin 3 = Data+.
3. Ist der VMA432 an 5 V, GND und GPIO 14/TX angeschlossen?
4. Existiert `/dev/ttyAMA0`, und ist der Benutzer in der Gruppe `dialout`?
5. Ist am letzten Gerät ein 120-Ohm-DMX-Terminator gesteckt?

## Netzwerk und Sicherheit

Die Anwendung enthält bewusst keine Benutzerverwaltung und ist für ein vertrauenswürdiges lokales Netz gedacht. Port 8000 nicht direkt ins Internet weiterleiten. Für Zugriff außerhalb des eigenen LANs ein VPN wie WireGuard oder Tailscale verwenden oder einen Reverse Proxy mit TLS und Authentifizierung vorschalten.

## Entwicklung und Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Technische Quellen

- [Velleman VMA432 Benutzerhandbuch](https://m.media-amazon.com/images/I/81mam8nSMHL.pdf)
- [Raspberry Pi Dokumentation: UART-Konfiguration](https://www.raspberrypi.com/documentation/computers/configuration.html#configure-uarts)
- [Raspberry Pi Firmware: Device-Tree-Overlay-Referenz](https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README)
- [Texas Instruments SN75176B](https://www.ti.com/product/SN75176B)
- [Analog Devices MAX485](https://www.analog.com/en/products/max485.html)
