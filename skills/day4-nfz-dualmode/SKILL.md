---
name: bloodai-day4-nfz-dualmode
description: "Dzień 4 hackathonu BloodAI: integracja NFZ API Terminy Leczenia, dual mode (pacjent/klinicysta), trendy czasowe. To killer features, które odróżniają od konkurencji."
---

# Dzień 4: NFZ Kolejki + Dual Mode + Trendy

## Cel dnia
Na koniec dnia masz: wyniki triażu połączone z realnymi danymi NFZ o kolejkach ("Nefrolog Warszawa — pierwszy termin za 47 dni"), przełącznik pacjent/klinicysta, i podstawowe porównanie trendów.

## Checklist zadań

### Blok 1: NFZ API Integration (3-4h) ⭐ KILLER FEATURE
- [ ] Zmapuj 8 klas BERT → nazwy świadczeń NFZ:
```json
{
  "poz": "PORADNIA (GABINET) LEKARZA POZ",
  "gastro": "PORADNIA GASTROENTEROLOGICZNA",
  "hema": "PORADNIA HEMATOLOGICZNA",
  "neph": "PORADNIA NEFROLOGICZNA",
  "sor": null,
  "cardio": "PORADNIA KARDIOLOGICZNA",
  "pulmo": "PORADNIA CHORÓB PŁUC",
  "hepa": "PORADNIA HEPATOLOGICZNA"
}
```
(SOR = brak kolejki, to nagły — pokaż info "Jedź na najbliższy SOR!")

- [ ] Backend endpoint `GET /nfz/queues`:
```python
@app.get("/nfz/queues")
async def get_nfz_queues(
    specialty: str,        # np. "PORADNIA NEFROLOGICZNA"
    province: str = "07",  # 07 = mazowieckie
    locality: str = None   # np. "Warszawa"
):
    url = f"https://api.nfz.gov.pl/app-itl-api/queues"
    params = {
        "case": 1,            # 1 = stabilny
        "benefit": specialty,
        "province": province,
        "locality": locality or "",
        "format": "json",
        "limit": 10,
        "api-version": "1.3"
    }
    # Parse response → extract:
    # - provider (nazwa placówki)
    # - place (adres)
    # - dates.date (pierwszy wolny termin)
    # - statistics.provider-data.awaiting (liczba oczekujących)
    # - statistics.provider-data.average-period (średni czas oczekiwania w dniach)
    # - phone
```

- [ ] Frontend: sekcja "Znajdź specjalistę" po triażu
  - Dla każdej specjalizacji flagged (prob > threshold):
    - Karta z danymi NFZ: nazwa placówki, adres, pierwszy wolny termin, czas oczekiwania, telefon
    - Badge: "NFZ" (zielony) vs "Prywatnie" (niebieski)
    - Sortowanie: wg terminu (najszybciej), wg odległości, wg oczekujących
  - Jeśli SOR flagged: DUŻY CZERWONY BANNER "Zalecamy niezwłoczny kontakt z pogotowiem lub SOR"
  - Przycisk "Zadzwoń" (tel: link), "Nawiguj" (Google Maps link)

- [ ] Geolokalizacja:
  - `navigator.geolocation` → automatycznie wykryj województwo/miasto
  - Fallback: dropdown z województwami
  - Mapowanie lokalizacji → kod województwa NFZ (01-16)

- [ ] Mapa (Leaflet):
  - Piny z placówkami NFZ
  - Popup: nazwa, termin, czas oczekiwania, telefon
  - Kolor pinu: zielony (krótki termin) → czerwony (długi)

- [ ] Cache: cachuj wyniki NFZ na 1h (żeby nie spamować API)

### Blok 2: Dual Mode — Pacjent / Klinicysta (2h)
- [ ] Przełącznik w headerze: 👤 Pacjent ↔ 🩺 Klinicysta
- [ ] Stan w React context/state

**Tryb pacjenta:**
- [ ] Wyniki triażu: zamiast "Nefrologia: 92%" → "Zalecamy konsultację nefrologiczną" (sygnalizator: 🔴🟡🟢)
- [ ] Bez surowych prawdopodobieństw, bez attention scores
- [ ] Wyjaśnienia Opus: prompt pacjentowy (prostym językiem)
- [ ] Disclaimer widoczny: "To narzędzie wspiera, nie zastępuje konsultacji lekarskiej"
- [ ] NFZ kolejki: focus na "kiedy mogę się dostać"

**Tryb kliniczny:**
- [ ] Pełne prawdopodobieństwa 8 klas z threshold markers
- [ ] Attention heatmap ze scorami
- [ ] ECE confidence (jeśli dostępne)
- [ ] Wyjaśnienia Opus: prompt kliniczny (medyczny język)
- [ ] Opcja "Dual review" gdy >1 specjalizacja > 0.5
- [ ] Przycisk "Generuj raport" (do wydruku)

### Blok 3: Trendy Czasowe — basic (1-2h)
- [ ] Przycisk "Porównaj z wcześniejszymi wynikami"
- [ ] Drugi formularz (lub upload drugiego skanu)
- [ ] Tabela porównawcza:
```
Parametr    | Poprzedni  | Obecny   | Zmiana | Trend
Kreatynina  | 1.8 mg/dL  | 4.8 mg/dL | +3.0  | ⬆️⬆️ (szybki wzrost)
HGB         | 13.5 g/dL  | 12.0 g/dL | -1.5  | ⬇️ (spadek)
```
- [ ] Opus 4.7 interpretacja trendu:
```
Prompt:
"Pacjent {wiek}, {płeć}. Porównanie wyników:
{tabela zmian}
Okres: {data1} → {data2}

Zinterpretuj kliniczne znaczenie trendów (max 100 słów).
Które zmiany są niepokojące? Czy tempo zmian jest istotne?"
```

### Blok 4: Polish + Edge Cases (1h)
- [ ] Loading states na NFZ API (może być wolne)
- [ ] Error handling: NFZ niedostępne → "Dane kolejek chwilowo niedostępne, spróbuj za chwilę"
- [ ] Empty state: brak wyników w okolicy → "Brak wyników. Spróbuj powiększyć obszar wyszukiwania."
- [ ] Mobile responsive sprawdzenie

## Self-assessment na koniec dnia

| Pytanie | Score |
|---------|-------|
| Czy NFZ kolejki pokazują realne terminy z API? | /5 |
| Czy dual mode przełącza widok sensownie? | /5 |
| Czy tryb pacjenta NIE pokazuje surowych liczb? | /5 |
| Czy trendy są czytelne i Opus interpretuje? | /5 |
| Czy cały flow skan→triage→explain→NFZ działa end-to-end? | /5 |

**25/25** = jutro tylko polish i demo prep
**20-24** = solidnie, jutro morning fix + demo
**15-19** = NFZ i dual mode MUSZĄ działać — trendy opcjonalne
**<15** = uprość: NFZ najpierw, dual mode drugiej kolejności, trendy drop

## NFZ API — uwagi techniczne
- API jest publiczne, bez klucza API
- Rate limit: brak udokumentowanego, ale bądź kulturalny (cache!)
- Odpowiedzi paginowane (25/stronę), użyj `limit=10`
- Dane aktualizowane przez placówki codziennie w dni robocze
- Parametr `case`: 1=stabilny, 2=pilny — użyj 1 dla normalnego triażu
- Kody województw: 01-16 (07=mazowieckie, 06=lubelskie, etc.)
