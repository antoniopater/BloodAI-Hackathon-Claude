---
name: bloodai-day2-frontend
description: "Dzień 2 hackathonu BloodAI: React frontend — formularz, wizualizacja triażu, tłumacz parametrów prostym językiem, attention heatmap. Kontrola postępu i ocena na koniec dnia."
---

# Dzień 2: Frontend Core + Tłumacz Parametrów

## Cel dnia
Na koniec dnia masz: działający React UI z formularzem wpisywania wyników, tłumaczem parametrów prostym językiem, wizualizacją 8 klas triażu z attention heatmap, i adaptive interview. Połączony z backendem z dnia 1.

## Rano: sprawdź status z dnia 1
- [ ] Trening się zakończył? Sprawdź metryki (ROC AUC, ECE)
- [ ] `/predict` endpoint działa? Przetestuj kilka scenariuszy
- [ ] Jeśli model nie dał dobrych wyników — potunuj thresholds, nie panikuj

## Checklist zadań

### Blok 1: React Setup + Input Form (2-3h)
- [ ] React app (Vite lub Next.js)
- [ ] Layout: dark theme, medyczny/kliniczny design
- [ ] Formularz wpisywania wyników:
  - Pola: wiek, płeć, HGB, HCT, PLT, MCV, WBC, Kreatynina, ALT
  - Walidacja: min/max per parametr
  - Kolorowe obramowania wg statusu: ✅ norma (zielony), ⚠️ poza normą (żółty), 🚨 krytyczne (czerwony)
  - Presety demo: "Nefrologia", "Multi-label", "Norma" — one-click fill
- [ ] Przycisk "Analizuj" → POST do `/predict`

### Blok 2: Tłumacz Parametrów — KLUCZOWY FEATURE (2-3h)
- [ ] Przy każdym polu parametru: rozwijany panel "Co to oznacza?"
- [ ] Dwa poziomy informacji:
  1. **Statyczny** (zawsze widoczny): nazwa parametru + "za co odpowiada" (1 zdanie)
  2. **Dynamiczny** (po kliknięciu "Wyjaśnij"): Opus 4.7 generuje kontekstowy opis

Przykłady statycznych opisów (hardkodowane, szybkie):
```
HGB: "Hemoglobina — białko przenoszące tlen w krwi. Niska = możliwa anemia."
HCT: "Hematokryt — jaki procent krwi stanowią czerwone krwinki."
PLT: "Płytki krwi — odpowiadają za krzepnięcie. Za mało = ryzyko krwawień."
MCV: "Średnia objętość krwinki — pomaga rozróżnić typy anemii."
WBC: "Białe krwinki — armia odpornościowa. Za dużo = możliwa infekcja lub zapalenie."
Kreatynina: "Odpad z pracy mięśni usuwany przez nerki. Wysoka = nerki mogą mieć problem."
ALT: "Enzym wątrobowy. Wysoki = możliwe uszkodzenie wątroby."
```

- [ ] Dynamiczne wyjaśnienia (Opus 4.7 API call):
  - Prompt: "Pacjent {wiek} lat, {płeć}. Parametr {nazwa} = {wartość} {jednostka} (norma: {low}-{high}). Wyjaśnij prostym językiem co to oznacza dla tego pacjenta, max 2 zdania. Nie diagnozuj, nie strasz."
  - Wywoływany on-demand (przycisk), nie automatycznie
  - Cache: raz wygenerowany opis trzymaj w state do końca sesji
  - Loading state: skeleton/typing animation podczas generowania

- [ ] Wyjaśnienie kombinacji (po kliknięciu "Analizuj"):
  - Opus 4.7 dostaje WSZYSTKIE parametry → generuje krótkie podsumowanie wzajemnych zależności
  - Np. "Niska hemoglobina w połączeniu z wysoką kreatyniną może wskazywać na anemię towarzyszącą chorobie nerek"

### Blok 3: Wizualizacja Triażu (2h)
- [ ] 8 horizontal bars z prawdopodobieństwami (animowane, kolorowe)
- [ ] Threshold marker na każdym barze
- [ ] Klasy powyżej threshold oznaczone jako "zalecane"
- [ ] Attention heatmap:
  - Pionowy bar chart lub heatmap
  - Parametry posortowane od najwyższej attention do najniższej
  - Kolorowanie: czerwony (wysoka attention) → niebieski (niska)
  - Tooltip z wartością attention score

### Blok 4: Adaptive Interview (1h)
- [ ] Jeśli parametr poza normą → wyskakuje pytanie z banku (GET `/questions/{param}`)
- [ ] UI: modal lub inline card z pytaniem + tak/nie
- [ ] Odpowiedź dodawana do tokenu → re-predict
- [ ] Max 3 pytania (żeby nie zanudzić)

### Blok 5: Animacje + Polish (1h)
- [ ] Płynne przejścia: input → loading (spinner + "Analiza BERT...") → results
- [ ] Fade-in na wynikach
- [ ] Typing animation na wyjaśnieniach Opus
- [ ] Mobile responsive (podstawowy)

## Self-assessment na koniec dnia

| Pytanie | Score |
|---------|-------|
| Czy formularz wygląda profesjonalnie i działa? | /5 |
| Czy tłumacz parametrów jest zrozumiały dla nie-medyka? | /5 |
| Czy wizualizacja triażu (bars + attention) jest czytelna? | /5 |
| Czy Opus 4.7 jest zintegrowany z wyjaśnieniami? | /5 |
| Czy whole flow działa end-to-end (input → predict → results)? | /5 |

**25/25** = frontend gotowy, jutro skupiasz się na Opus features
**20-24** = dobrze, drobny polish jutro rano
**15-19** = uprość — skup się na core flow, attention i Opus mogą poczekać
**<15** = alarm — poświęć jutro rano na dokończenie frontendu

## Fallback
- Tłumacz parametrów: jeśli Opus API nie działa → hardkodowane opisy (statyczne) wystarczą
- Attention heatmap: może być prosty bar chart zamiast fancy heatmap
- Adaptive interview: może być opcjonalny, nie blokuj triażu
