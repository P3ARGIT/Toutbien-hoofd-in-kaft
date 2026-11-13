# Toutbien expo-speler

Voor een Raspberry Pi 5 met Raspberry Pi OS 64-bit **met desktop**. In standby staat de rode titel **sorry voor het ongemak sebiet** (#d61321) op een crèmekleurig scherm (#f3eadc) en speelt de WAV continu door. Linksboven staat een **rood bolletje** bij een laag sensorsignaal en een **groen bolletje** bij een hoog signaal. Na detectie verschijnt onder de titel **3**, **2** en **1**, elk één seconde. Daarna stopt het standbygeluid en begint de productvideo vanaf het begin. Na afloop springt het scherm meteen naar zwart en blijft het drie seconden stil. Daarna verschijnen de standbytitel en het standbygeluid opnieuw. Elke nieuwe sensorpuls in standby start de video weer vanaf het begin. Als het sensorsignaal tijdens een lopende video 20 seconden wegblijft, stopt de video en verschijnt standby.

## Aansluiten

Haal eerst de voeding van de Pi. Controleer de opschriften op de **WPSE314** en volg de draden vanaf de module. In de foto zijn de stekkers over de pinnummers geschoven. De kleuren hieronder gelden alleen als ze overeenkomen met de opschriften.

| WPSE314 | Gebruikelijke kleur | Fysieke pin Raspberry Pi 5 |
| --- | --- | --- |
| VCC | Rood | **2**, 5 V voeding |
| GND | Zwart | **6**, massa |
| OUT | Wit | **11**, BCM GPIO17 |

De module krijgt 5 V op VCC en levert volgens Velleman 0 V of circa 3 V op OUT. Verbind **nooit 5 V** met GPIO17. Gebruik de fysieke nummers van de 40-pins connector. [WPSE314-specificaties](https://www.velleman.eu/products/view/pir-motion-sensor-wpse314/?id=459220&lang=en) · [Officiële pinout](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio)

Richt de PIR op de opening, weg van passerend publiek. Zet de gevoeligheid laag en de tijdinstelling op de kortste stand. Tijdens de eerste 60 seconden na het opstarten van de Pi speelt standby al terwijl de PIR opwarmt. Bij het starten wacht de app eerst op een stabiel laag signaal. Daarna triggert een overgang naar hoog de countdown. Een stil hoofd kan het bewegingssignaal laten wegvallen, en na vertrek blijft het signaal gedurende de ingestelde tijd nog hoog. Test daarom zowel met een stil hoofd als met iemand die langs het paneel loopt.

Sluit het scherm aan via micro-HDMI. Gebruik de speaker van het scherm via HDMI, een USB-speaker of een actieve speaker via een USB-geluidsadapter. Selecteer de uitgang via het luidsprekericoon op de Pi voordat je de speler start. Beide geluiden gebruiken de standaard audio-uitgang van de desktopsessie. De speler zet die uitgang bij het starten op 100% en heft dempen op.

## Installeren

Open **Terminal op het Pi-bureaublad**, lokaal of via **Screen sharing** in Raspberry Pi Connect. Gebruik je gewone desktopaccount.

~~~bash
sudo apt-get install -y git
cd ~
git clone https://github.com/P3ARGIT/Toutbien-hoofd-in-kaft.git
cd Toutbien-hoofd-in-kaft
bash install.sh
~~~

Via een overgezet archief kun je in de uitgepakte map direct **bash install.sh** uitvoeren. De installatie kopieert de speler, de originele video en het standbygeluid naar **~/.local/share/toutbien** en voegt hem toe aan de automatische start van je desktopaccount. Een volgende installatie overschrijft die kopie, bijvoorbeeld nadat je de bestanden in de projectmap hebt vervangen.

Voor opstarten zonder toetsenbord kies je via **sudo raspi-config** voor **Desktop Autologin** en zet je **Screen Blanking** uit. Herstart daarna. [Raspberry Pi OS-instellingen](https://www.raspberrypi.com/documentation/computers/configuration.html)

## Lettertype

De speler gebruikt **Obviously** als het lettertype op de Pi is geïnstalleerd. Plaats een gelicentieerd OTF- of TTF-bestand in `~/.local/share/fonts/`, voer `fc-cache -f` uit en heropen Toutbien. Zonder Obviously gebruikt de standbytitel DejaVu Sans. [Obviously bij Adobe Fonts](https://fonts.adobe.com/fonts/obviously)

## Starten en afsluiten

Dubbelklik op **Toutbien** op het bureaublad of kies **Toutbien expo-speler** in het toepassingenmenu onder **Geluid en video**. Verschijnt een vraag over het bureaubladbestand, kies **Uitvoeren**. Druk in het spelersvenster op **P** voor portrait (90° tegen de klok in, zoals bij de rechtop gemonteerde monitor) of **L** voor landscape. De app start in landscape. In portrait behoudt de video zijn beeldverhouding en kan er boven en onder een zwarte strook staan. Druk op **Q** of **Esc** om het scherm en geluid te sluiten. Automatisch opstarten bij de volgende desktoplogin blijft actief.

## Testen

Test vóór de eerste herstart eventueel zonder sensor vanuit een terminal op de desktop. Na een herstart kun je de bestaande speler eerst stoppen met **pkill -f '[t]outbien/player.py'**.

~~~bash
python3 ~/.local/share/toutbien/player.py --test
~~~

Druk Enter om de video te starten en kijk of hij aan het einde naar standby terugkeert. Druk opnieuw Enter om het wegvallen van het signaal te simuleren. Zodra standby terug is, kun je met Enter een nieuwe weergave activeren. Typ **q** en druk Enter om te stoppen. Als de terminal achter het videovenster staat, gebruik je **Alt+Tab** om terug te schakelen. Start de normale modus daarna met **bash ~/.local/share/toutbien/start.sh**, of herstart de Pi. Het log staat standaard in **~/.local/state/toutbien/player.log**.

### PIR reageert niet

Sluit de speler af met **Q** of **Esc** en voer dit uit:

~~~bash
python3 ~/.local/share/toutbien/player.py --sensor-test
~~~

Wacht na inschakelen ongeveer 60 seconden. Controleer eerst of je **GPIO17 = 0** ziet wanneer niemand beweegt. Beweeg daarna dwars door het zichtveld van de sensor. Je hoort **GPIO17 = 1** te zien. Stop met **Ctrl+C**.

- Blijft het signaal **0**, haal de voeding van de Pi en controleer VCC, GND en OUT aan beide kanten. Verhoog de gevoeligheid of richt de sensor opnieuw.
- Blijft het signaal **1**, maak het detectiegebied vrij en zet de tijdinstelling van de sensor korter. Voor een nieuwe detectie in standby moet het signaal eerst terug naar **0** en daarna weer naar **1**.
- Wisselt het signaal wel, gebruik **--test** hierboven om de video los van de sensor te testen. Bekijk bij een fout **tail -n 30 ~/.local/state/toutbien/player.log**. Bij gebruik van een lichtsluis voeg je **--beam** toe aan **--sensor-test**.

## Exacte aanwezigheidsdetectie met een lichtsluis

Monteer een zender en ontvanger tegenover elkaar over de opening, op een plek waar het hoofd de straal onderbreekt. Gebruik een ontvanger met een **open-collector/open-drain-uitgang die bij een vrije straal naar GND trekt en bij onderbreking loslaat**. Verbind de uitgang met fysieke pin 11 en de massa van de ontvanger met pin 6. Voed zender en ontvanger volgens hun eigen specificaties. De Pi trekt de signaallijn intern naar 3,3 V. Controleer vóór aansluiten dat de ontvanger geen hogere spanning op de lijn zet, ook via een interne pull-up.

Installeer vanuit de projectmap met **bash install.sh --beam** en herstart. In deze stand start de video zodra de onderbreking ongeveer 120 ms stabiel is. De reset volgt na 20 seconden met een vrije straal. De lichtsluis blijft een stil hoofd detecteren zolang dat de straal onderbreekt.
