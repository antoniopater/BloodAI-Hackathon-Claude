---
name: bloodai-day5-demo
description: "Dzień 5 hackathonu BloodAI: przygotowanie demo, deploy, pitch. Wszystko musi działać na żywo bez zacięć. Backup video. Finalna samoocena."
---

# Dzień 5: Demo Prep + Deploy

## Cel dnia
Na koniec dnia masz: zdeployowaną aplikację, przećwiczony 2-minutowy pitch, 4 scenariusze demo przetestowane, backup video nagrane.

## Rano: Full E2E Test (2h)
- [ ] Przejdź cały flow od zera, nagrywając ekran:
  1. Otwórz apkę → skan kartki z wynikami
  2. Podgląd OCR → zatwierdź
  3. Tłumacz parametrów (kliknij "co to znaczy" na 2-3 parametrach)
  4. Analizuj → wyniki triażu + attention
  5. Przełącz tryb (pacjent ↔ klinicysta)
  6. Opus wyjaśnienie
  7. NFZ kolejki → pokaż placówki
  8. (opcjonalnie) Trendy — porównaj z wcześniejszymi
- [ ] Zanotuj co się zacina, co jest wolne, co wygląda źle
- [ ] Napraw krytyczne bugi (max 1h na fixy)

## Deploy (1-2h)
- [ ] Backend:
  - Railway / Render / Fly.io
  - Upewnij się: model ładuje się przy starcie (cold start < 30s)
  - Health check endpoint: `GET /health`
  - CORS ustawione na frontend domain
- [ ] Frontend:
  - Vercel (najprościej z React/Next.js)
  - Environment variables: API URL, Anthropic API key
- [ ] Test na deploy: otwórz na telefonie + laptopie → cały flow działa

## Demo Script — 4 scenariusze (przygotuj i przećwicz)

### Scenariusz 1: 📷 "Skan kartki" (WOW moment — zaczynaj od tego!)
```
"Wyobraźcie sobie: pacjent wychodzi z laboratorium z kartką wyników.
Nie wie co oznaczają te liczby. Nie wie do kogo iść.
[robi zdjęcie kartki telefonem]
System rozpoznaje wyniki, porównuje z normami Z TEJ kartki...
[pokazuje auto-fill + weryfikację]
...i tłumaczy każdy parametr prostym językiem.
[klika 'Co to oznacza?' na kreatyninie]
"
```

### Scenariusz 2: 🔬 "Prosty case — nefrologia"
```
"Mężczyzna, 60 lat, wysoka kreatynina 4.8.
[wpisuje ręcznie lub używa preset]
Model BERT, trenowany na 260 tysiącach danych klinicznych,
natychmiast identyfikuje: Nefrologia z 99% prawdopodobieństwem.
[pokazuje attention map]
Patrzcie — model skupia attention na tokenie CREATININE_Q9.
To jest interpretowalne AI — lekarz widzi DLACZEGO.
[przełącza na tryb pacjenta]
A pacjent widzi: 'Zalecamy konsultację nefrologiczną.'
"
```

### Scenariusz 3: 🏥 "NFZ kolejki" (killer feature)
```
"Ale gdzie iść? System łączy się z publicznym API NFZ...
[klika 'Znajdź specjalistę']
Poradnia nefrologiczna w Warszawie — NFZ: pierwszy termin za 47 dni.
Prywatnie: za 3 dni.
[pokazuje mapę z placówkami]
Pacjent może od razu zadzwonić lub nawigować.
W Polsce czeka się średnio 4 miesiące na specjalistę.
My skracamy ten czas do 60 sekund decyzji."
```

### Scenariusz 4: 🚨 "Multi-label — kobieta 70 lat" (pokaz mocy)
```
"Kobieta 70 lat, ciężka anemia, niewydolność nerek,
infekcja, objawy kardiologiczne.
[preset 'Multi-label']
Model przewiduje 5 specjalizacji jednocześnie —
to jest multi-label, nie single-label.
Opus 4.7 weryfikuje: 'Zgadzam się z routingiem BERT.'
A teraz patrzcie na attention — rozproszona
po wielu tokenach, bo to złożony przypadek."
```

## Pitch — 2 minuty (wyucz się!)

```
[10s] PROBLEM:
"W Polsce pacjent czeka średnio 4 miesiące na specjalistę.
190 dni na endokrynologa. A zaczyna się od kartki z wynikami,
której nie rozumie."

[20s] SOLUTION:
"BloodAI: zeskanuj wyniki badań krwi — AI tłumaczy co oznaczają,
mówi do jakiego specjalisty iść, i pokazuje kolejki NFZ z terminami."

[60s] DEMO:
[Scenariusz 1: skan → auto-fill → tłumacz → triage → NFZ]

[20s] TECH:
"Pod spodem: dedykowany model BERT trenowany na danych klinicznych
z cost-sensitive loss i attention interpretability.
NIE wrapper na LLM — Opus 4.7 jest warstwą inteligencji NAD modelem:
Vision do OCR, tłumaczenie, weryfikacja, analiza trendów."

[10s] DIFFERENTIATOR:
"Żadna istniejąca apka nie łączy walidowanego modelu medycznego,
tłumaczenia prostym językiem, i realnych danych NFZ o kolejkach."
```

## Backup Video (1h)
- [ ] Nagraj cały flow (OBS / screen record)
- [ ] 2-3 minuty, clean run
- [ ] Upload na YouTube/Google Drive (unlisted)
- [ ] Link w README

## Final Checklist
- [ ] Repo publiczne na GitHubie
- [ ] README kompletne: opis, architektura, setup, screenshots
- [ ] Licencja MIT w pliku LICENSE
- [ ] requirements.txt / package.json aktualne
- [ ] Brak hardkodowanych secrets (użyj env vars)
- [ ] App działa na deploy URL
- [ ] App działa na telefonie (mobile test)
- [ ] Backup video nagrane

## FINALNA SAMOOCENA — Hackathon Scorecard

```
╔══════════════════════════════════════════════════╗
║           BLOODAI — FINAL ASSESSMENT             ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║  IMPACT (30%)                    /10  →    /3.0  ║
║  ├─ Realny problem (kolejki PL):      /10        ║
║  ├─ Kto korzysta (pacjent+lekarz):    /10        ║
║  ├─ Bliskość do produktu:             /10        ║
║  └─ Problem statement fit (#1):       /10        ║
║                                                  ║
║  DEMO (25%)                      /10  →    /2.5  ║
║  ├─ Działa end-to-end na żywo:        /10        ║
║  ├─ "Wow" moment (skan/NFZ):          /10        ║
║  └─ Wizualnie profesjonalne:          /10        ║
║                                                  ║
║  OPUS 4.7 USE (20%)             /10  →    /2.0  ║
║  ├─ Ile sposobów użycia (cel 4+):     /10        ║
║  ├─ Beyond basic (nie chatbot):       /10        ║
║  └─ Zaskoczenie (hybryda ML+LLM):    /10        ║
║                                                  ║
║  DEPTH & EXECUTION (20%)        /10  →    /2.0  ║
║  ├─ Jakość kodu i architektury:       /10        ║
║  ├─ Edge cases i error handling:      /10        ║
║  └─ Iteracja i craft:                /10        ║
║                                                  ║
║  ══════════════════════════════════════════════   ║
║  TOTAL:                              /10.0       ║
╚══════════════════════════════════════════════════╝
```

## Ostatnia rada
Na demo: **nie tłumacz technologii — POKAŻ JĄ.**
Mniej mówienia, więcej klikania. Sędziowie zapamiętają moment
kiedy zrobiłeś zdjęcie kartki i system sam ją odczytał,
nie slajd z architekturą BERT.
