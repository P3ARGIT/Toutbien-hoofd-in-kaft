# Toutbien expo-speler

Voor een Raspberry Pi 5 met Raspberry Pi OS 64-bit **met desktop**. In standby staat de witte titel **sorry voor het ongemak sebiet** op een zwart scherm en speelt de WAV continu door. Bij een actief sensorsignaal stopt het standbygeluid en start de productvideo met geluid vanaf het begin. In de laatste seconde fadet het beeld naar zwart. Daarna verschijnt de standbytitel en keert het geluid terug, ook als de sensor nog actief is. Na 20 seconden zonder sensorsignaal wordt de speler opnieuw gereed voor de volgende bezoeker. Als de video dan nog loopt, stopt hij en verschijnt standby.

## Aansluiten

Haal eerst de voeding van de Pi. Controleer de opschriften op de **WPSE314** en volg de draden vanaf de module. In de foto zijn de stekkers over de pinnummers geschoven. De kleuren hieronder gelden alleen als ze overeenkomen met de opschriften.

| WPSE314 | Gebruikelijke kleur | Fysieke pin Raspberry Pi 5 |
| --- | --- | --- |
| VCC | Rood | **2**, 5 V voeding |
| GND | Zwart | **6**, massa |
| OUT | Wit | **11**, BCM GPIO17 |

De module krijgt 5 V op VCC en levert volgens Velleman 0 V of circa 3 V op OUT. Verbind **nooit 5 V** met GPIO17. Gebruik de fysieke nummers van de 40-pins connector. [WPSE314-specificaties](https://www.velleman.eu/products/view/pir-motion-sensor-wpse314/?id=459220&lang=en) · [Officiële pinout](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio)

Richt de PIR op de opening, weg van passerend publiek. Zet de gevoeligheid laag en de tijdinstelling op de kortste stand. Na starten negeert de speler de sensor 60 seconden terwijl standby al speelt. Een stil hoofd kan het bewegingssignaal laten wegvallen, en na vertrek blijft het signaal gedurende de ingestelde tijd nog hoog. Test daarom zowel met een stil hoofd als met iemand die langs het paneel loopt.

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

Via een overgezet archief kun je in de uitgepakte map direct **bash install.sh** uitvoeren. De installatie kopieert de speler en beide mediabestanden naar **~/.local/share/toutbien** en voegt hem toe aan de automatische start van je desktopaccount. Een volgende installatie overschrijft die kopie, bijvoorbeeld nadat je de bestanden in de projectmap hebt vervangen.

Voor opstarten zonder toetsenbord kies je via **sudo raspi-config** voor **Desktop Autologin** en zet je **Screen Blanking** uit. Herstart daarna. [Raspberry Pi OS-instellingen](https://www.raspberrypi.com/documentation/computers/configuration.html)

## Starten en afsluiten

Dubbelklik op **Toutbien** op het bureaublad of kies **Toutbien expo-speler** in het toepassingenmenu onder **Geluid en video**. Verschijnt een vraag over het bureaubladbestand, kies **Uitvoeren**. Druk in het spelersvenster op **Q** of **Esc** om het scherm en geluid te sluiten. Automatisch opstarten bij de volgende desktoplogin blijft actief.

## Testen

Test vóór de eerste herstart eventueel zonder sensor vanuit een terminal op de desktop. Na een herstart kun je de bestaande speler eerst stoppen met **pkill -f '[t]outbien/player.py'**.

~~~bash
python3 ~/.local/share/toutbien/player.py --test
~~~

Druk Enter om de video te starten en kijk of hij aan het einde naar standby terugkeert. Druk opnieuw Enter om het wegvallen van het signaal te simuleren. Na 20 seconden kun je een nieuwe weergave activeren. Typ **q** en druk Enter om te stoppen. Als de terminal achter het videovenster staat, gebruik je **Alt+Tab** om terug te schakelen. Start de normale modus daarna met **bash ~/.local/share/toutbien/start.sh**, of herstart de Pi. Het log staat standaard in **~/.local/state/toutbien/player.log**.

### PIR reageert niet

Sluit de speler af met **Q** of **Esc** en voer dit uit:

~~~bash
python3 ~/.local/share/toutbien/player.py --sensor-test
~~~

Wacht na inschakelen ongeveer 60 seconden. Controleer eerst of je **GPIO17 = 0** ziet wanneer niemand beweegt. Beweeg daarna dwars door het zichtveld van de sensor. Je hoort **GPIO17 = 1** te zien. Stop met **Ctrl+C**.

- Blijft het signaal **0**, haal de voeding van de Pi en controleer VCC, GND en OUT aan beide kanten. Verhoog de gevoeligheid of richt de sensor opnieuw.
- Blijft het signaal **1**, maak het detectiegebied vrij en zet de tijdinstelling van de sensor korter. Na een afgespeelde video wacht de speler op 20 aaneengesloten seconden **0**. Beweging binnen die periode zet de teller terug.
- Wisselt het signaal wel, gebruik **--test** hierboven om de video los van de sensor te testen. Bekijk bij een fout **tail -n 30 ~/.local/state/toutbien/player.log**. Bij gebruik van een lichtsluis voeg je **--beam** toe aan **--sensor-test**.

## Exacte aanwezigheidsdetectie met een lichtsluis

Monteer een zender en ontvanger tegenover elkaar over de opening, op een plek waar het hoofd de straal onderbreekt. Gebruik een ontvanger met een **open-collector/open-drain-uitgang die bij een vrije straal naar GND trekt en bij onderbreking loslaat**. Verbind de uitgang met fysieke pin 11 en de massa van de ontvanger met pin 6. Voed zender en ontvanger volgens hun eigen specificaties. De Pi trekt de signaallijn intern naar 3,3 V. Controleer vóór aansluiten dat de ontvanger geen hogere spanning op de lijn zet, ook via een interne pull-up.

Installeer vanuit de projectmap met **bash install.sh --beam** en herstart. In deze stand start de video zodra de onderbreking ongeveer 120 ms stabiel is. De reset volgt na 20 seconden met een vrije straal. De lichtsluis blijft een stil hoofd detecteren zolang dat de straal onderbreekt.
