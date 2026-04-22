# BloodAI Triage + Specialist Finder — Hackathon Plan

## Koncept jednozdaniowy (elevator pitch)
**"Zeskanuj kartkę z wynikami badań krwi → AI tłumaczy co oznaczają prostym językiem → mówi do jakiego specjalisty iść → pokazuje kolejki NFZ i prywatnych lekarzy z terminami, ocenami i telefonem."**

---

## Architektura

```
┌──────────────────── FRONTEND (React JSX) ──────────────────────────────┐
│                                                                         │
│  0. SCAN         1. INPUT         2. TRIAGE        3. FIND DOCTOR      │
│  ┌──────────┐   ┌───────────┐   ┌──────────────┐  ┌────────────────┐  │
│  │📷 Camera │   │ Manual or │   │ 8-class bars │  │ NFZ kolejki    │  │
│  │  or 📄   │──▶│ auto-fill │──▶│ + attention  │─▶│ + prywatni     │  │
│  │ PDF/foto │   │ + explain │   │ + explanation│  │ mapa, terminy  │  │
│  └──────────┘   │ + trends  │   │ + dual mode  │  │ tel, nawigacja │  │
│                  └───────────┘   └──────────────┘  └────────────────┘  │
│                  ↕ parametry       ↕ tryb                               │
│              tłumaczone prostym   pacjent / klinicysta                  │
│              językiem + normy                                           │
│              z kartki lub domyślne                                      │
└───┬──────────────┬──────────────────┬──────────────┬──────────┬────────┘
    │              │                  │              │          │
┌───▼────┐    ┌────▼────┐      ┌─────▼─────┐  ┌────▼────┐ ┌───▼──────┐
│Opus 4.7│    │Opus 4.7 │      │ BERT Model│  │NFZ API  │ │Google    │
│ Vision │    │ Explain │      │ (FastAPI) │  │Terminy  │ │Places API│
└────────┘    └─────────┘      └───────────┘  │Leczenia │ └──────────┘
- OCR zdjęcia  - Tłumacz        - Inference    └─────────┘  - Prywatni
- Ekstrakcja    parametry       - Attention    - Kolejki     - Ratings
  wartości +    prostym         - Probabilities- Terminy     - Phone
  norm z kartki językiem                       - 14k placówek
- PDF parsing  - Kontekstowe                   - Bezpłatne API
- Trend analysis wyjaśnienia
```

### Kluczowe feature'y aplikacji

**📷 Skan wyników (Camera/PDF):**
Użytkownik robi zdjęcie kartki z laboratorium lub wgrywa PDF. Opus 4.7 Vision:
1. Rozpoznaje parametry i wartości (OCR)
2. Rozpoznaje normy z tej samej kartki (każde lab ma swoje zakresy)
3. Automatycznie wypełnia formularz
4. Jeśli normy nieczytelne → fallback na domyślne z lab_norms.json

**📖 Tłumacz parametrów (prostym językiem):**
Przy każdym parametrze użytkownik widzi:
- Co to jest (np. "Kreatynina — pokazuje jak dobrze pracują Twoje nerki")
- Co oznacza jego wynik (np. "Twój wynik 4.8 jest znacznie powyżej normy — nerki mogą mieć trudności z filtrowaniem")
- Opus 4.7 generuje te opisy dynamicznie, uwzględniając wiek, płeć i kombinację wszystkich wyników

**🔬 Kontekst kombinacji:**
Opus 4.7 rozumie że niska hemoglobina + wysoka kreatynina razem to inna sytuacja niż każda osobno — generuje wyjaśnienie uwzględniające wzajemne zależności parametrów

**👤/🩺 Dual Mode — pacjent vs klinicysta:**
- **Tryb pacjenta**: uproszczony widok, bez surowych prawdopodobieństw, opisy prostym językiem, wyraźny disclaimer "skonsultuj z lekarzem", kolorowe sygnalizatory (zielony/żółty/czerwony)
- **Tryb kliniczny**: pełne prawdopodobieństwa 8 klas, attention heatmap, surowe wartości, ECE confidence, opcja dual review, raport PDF do wydruku
- Przełącznik w UI — ten sam model, inny sposób prezentacji wyników
- To rozwiązuje problem "pacjent się sam diagnozuje" — bo tryb pacjenta NIGDY nie pokazuje surowych liczb, tylko "zalecamy konsultację z nefrologiem"

**📈 Trendy czasowe (porównanie wyników):**
- Użytkownik może wrzucić 2+ zestawów wyników (np. z marca i z teraz)
- System pokazuje strzałki ↑↓ przy parametrach + wizualizację trendu
- Opus 4.7 interpretuje trend: "Kreatynina wzrosła z 1.8 do 4.8 w ciągu 3 miesięcy — to szybka progresja, która wymaga pilnej konsultacji nefrologicznej"
- To jest feature, którego konkurencja (TestResult.ai, Aima) NIE ma
- Lekarze patrzą na trendy, nie na pojedyncze wartości — to dodaje wiarygodność kliniczną

**🏥 NFZ Kolejki + Prywatni lekarze:**
Zamiast samego Google Places, integracja z publicznym API NFZ "Terminy Leczenia":
- `https://api.nfz.gov.pl/app-itl-api/queues` — pierwszy wolny termin, średni czas oczekiwania
- 14 000 placówek, aktualizowane co tydzień
- Po triażu: "Nefrolog w Warszawie — NFZ: pierwszy termin za 47 dni, prywatnie: 3 dni"
- Sortowanie: wg czasu oczekiwania, wg odległości, NFZ vs prywatnie
- To jest killer feature dla polskiego rynku — nikt tego nie łączy z triażem

---

## Plan pracy — dzień po dniu

### Dzień 1: Poniedziałek 21.04 — Pipeline + Fundament
**Cel: Pełny pipeline ML od zera + backend serwujący predykcje**

- [ ] Przygotować repo (GitHub, open source — wymagane!)
- [ ] Napisać do organizatorów: pytanie o checkpoint + open source po hackathonie
- [ ] **ML Pipeline (od zera — "New Work Only"):**
  - [ ] Skrypt preprocessingu: Synthea + MIMIC → hybrid corpus
  - [ ] Tokenizer: budowa vocab (~140 tokenów), kwantyzacja lab values
  - [ ] MLM pre-training skrypt (6 layers, 256 hidden, 8 heads)
  - [ ] Fine-tuning skrypt (multi-label, cost-sensitive focal loss)
  - [ ] Puścić trening w nocy (GPU) — rano checkpoint gotowy
- [ ] Postawić FastAPI endpoint: `/predict` — JSON z wartościami lab → 8 prawdopodobieństw + attention
- [ ] Endpoint `/lab_norms` — normy referencyjne (domyślne + override z kartki)
- [ ] Endpoint `/questions` — bank pytań (adaptive interview)
- [ ] README.md — opis projektu, setup, architektura

### Dzień 2: Wtorek 22.04 — Frontend core + Tłumacz parametrów
**Cel: Działający UI z inputem, wyjaśnieniami parametrów i wynikami triażu**

- [ ] React komponent: formularz wpisywania wyników (HGB, HCT, PLT, MCV, WBC, Creatinine, ALT, wiek, płeć)
- [ ] **🆕 Tłumacz parametrów (prostym językiem):**
  - [ ] Każdy parametr ma tooltip/panel: "Co to jest?", "Co oznacza Twój wynik?"
  - [ ] Kolorowe oznaczenie: ✅ norma, ⚠️ poza normą, 🚨 krytyczne
  - [ ] Opus 4.7 generuje dynamiczne opisy uwzględniając kontekst (wiek, płeć, kombinacje)
  - [ ] Cache opisów — żeby nie wywoływać API przy każdej zmianie wartości
- [ ] Wizualizacja wyników: 8 pasków prawdopodobieństwa z kolorami
- [ ] Attention heatmap — wizualizacja które parametry wpłynęły na decyzję
- [ ] Adaptive interview: wartość poza normą → pytanie → odpowiedź wpływa na predykcję
- [ ] Animacje: płynne przejścia między krokami

### Dzień 3: Środa 23.04 — Opus 4.7 Integration + Skan (KLUCZOWY DZIEŃ)
**Cel: Opus 4.7 jako warstwa inteligencji — skan, wyjaśnienia, second opinion**

- [ ] **📷 Camera/PDF Scan — ekstrakcja wyników:**
  - [ ] Upload zdjęcia (aparat/galeria) lub PDF z laboratorium
  - [ ] Opus 4.7 Vision → OCR → rozpoznanie parametrów + wartości
  - [ ] Rozpoznanie norm z kartki (każde lab ma swoje zakresy!)
  - [ ] Auto-fill formularza z wykrytych wartości
  - [ ] Podgląd: "Rozpoznaliśmy te wartości — sprawdź i zatwierdź"
  - [ ] Fallback: jeśli normy nieczytelne → domyślne z lab_norms.json
  - [ ] Obsługa: zdjęcie krzywe, słaba jakość, częściowo zasłonięte
- [ ] **Wyjaśnienia dla pacjenta**: wyniki triażu + attention → przystępny opis
- [ ] **Inteligentny interview**: Opus generuje kontekstowe follow-up pytania
- [ ] **"Second opinion"**: Opus weryfikuje BERT, flaguje rozbieżności
- [ ] **Raport PDF**: podsumowanie do pobrania/wydruku dla lekarza

### Dzień 4: Czwartek 24.04 — NFZ Kolejki + Dual Mode + Polish
**Cel: Integracja NFZ API, tryb pacjent/klinicysta, dopracowanie UX**

- [ ] **🏥 NFZ API "Terminy Leczenia" (KILLER FEATURE):**
  - [ ] Integracja z `https://api.nfz.gov.pl/app-itl-api/queues`
  - [ ] Mapowanie specjalizacji BERT → kody NFZ (np. Nefrologia → "PORADNIA NEFROLOGICZNA")
  - [ ] Pobieranie: pierwszy wolny termin, średni czas oczekiwania, adres, telefon
  - [ ] Filtrowanie po województwie/mieście (geolokalizacja użytkownika)
  - [ ] Widok porównawczy: NFZ (termin + czas oczekiwania) vs prywatni (Google Places + rating)
  - [ ] Sortowanie: najkrótszy czas oczekiwania, najbliżej, najlepsza ocena
- [ ] **👤/🩺 Dual Mode:**
  - [ ] Przełącznik: tryb pacjenta ↔ tryb kliniczny
  - [ ] Tryb pacjenta: sygnalizatory kolorowe, opisy bez liczb, disclaimer
  - [ ] Tryb kliniczny: pełne prawdopodobieństwa, attention, ECE, raport
- [ ] **📈 Trendy czasowe (basic):**
  - [ ] Przycisk "Dodaj wcześniejsze wyniki" → drugi zestaw wartości
  - [ ] Strzałki ↑↓ przy parametrach + delta
  - [ ] Opus 4.7 interpretuje kierunek zmiany
- [ ] Mapa z pinami (Leaflet) — NFZ placówki + prywatne
- [ ] Responsywność (mobile-first)
- [ ] Edge cases: brak wyników NFZ, błędy API, loading states

### Dzień 5: Piątek 25.04 — Demo prep + finalizacja
**Cel: Demo jest "wow", wszystko działa na żywo**

- [ ] End-to-end test: PDF upload → triage → explanation → find doctor — cały flow bez zacięć
- [ ] Demo script: przygotować 4 scenariusze:
  1. **📷 Skan kartki**: zrób zdjęcie wyników z lab → auto-fill → triage → lekarz (WOW moment!)
  2. **Prosty case**: mężczyzna 60 lat, wysoka kreatynina → tłumaczenie parametrów → Nefrologia → znajdź nefrologa
  3. **Complex multi-label**: kobieta 70 lat, anemia + niewydolność nerek → 5 specjalizacji → Opus wyjaśnia zależności → mapa
  4. **PDF upload**: wgraj PDF z laboratorium → pełen automat z normami z kartki
- [ ] Nagrać backup video (na wypadek problemów z live demo)
- [ ] Sprawdzić że repo jest publiczne, README kompletne, licencja open source
- [ ] Przygotować 2-min pitch:
  - Problem: "Pacjent dostaje wyniki badań, nie rozumie ich, nie wie do kogo iść, czeka miesiące na specjalistę — często niewłaściwego"
  - Statystyka: "W Polsce średni czas oczekiwania na specjalistę to 4 miesiące. Na endokrynologa — 190 dni."
  - Solution: "BloodAI: od wyników krwi do wizyty u specjalisty w 60 sekund"
  - Demo: live (skan kartki → tłumaczenie → triage → NFZ kolejki)
  - Tech: BERT multi-label (paper naukowy) + Opus 4.7 (Vision, NLG, verification) + NFZ API
  - Differentiator: "Nie jest to kolejny wrapper na ChatGPT. To dedykowany model medyczny z walidacją kliniczną, uzupełniony o Opus 4.7 jako warstwę inteligencji i realne dane NFZ."
  - Impact: oszczędność czasu pacjenta, lekarza POZ, i systemu opieki zdrowotnej

### Dzień 6: Sobota 26.04 — Hackathon day
- [ ] Ostatnie testy
- [ ] Deploy (Vercel frontend + Railway/Render backend)
- [ ] Demo!

---

## Jak maksymalizować punkty w każdej kategorii

### Impact (30%) — "Kto z tego korzysta?"
- **Pacjenci**: nie muszą czekać na lekarza POZ żeby wiedzieć do kogo iść; rozumieją swoje wyniki
- **Lekarze POZ**: automatyczny pre-screening, dual mode daje im profesjonalny widok z attention
- **System opieki zdrowotnej**: szybsze kierowanie = szybsze leczenie = mniejsze kolejki
- **Konkretne liczby do prezentacji**:
  - Średni czas oczekiwania na specjalistę: 4.1 miesiąca (WHC Barometer 2022)
  - Endokrynolog: 190 dni mediany (NFZ 2023)
  - Od wizyty POZ do operacji zastawki: 12.3 miesiąca
  - 5% zdrowych ludzi ma wyniki "poza normą" — pacjenci panikują niepotrzebnie
- **Unikalna wartość**: żadna istniejąca apka nie łączy triażu ML + tłumaczenia prostym językiem + realnych danych NFZ o kolejkach

### Demo (25%) — "Czy robi wrażenie na żywo?"
- 📷 Skan kartki telefonem = najsilniejszy "wow" moment — sędzia robi zdjęcie i widzi jak działa
- Tłumacz parametrów prostym językiem — "aaa, to DLATEGO muszę iść do nefrologa"
- Dual mode switch — przełączasz i widzisz ten sam wynik oczami pacjenta vs lekarza
- NFZ kolejki na żywo — "nefrolog w Warszawie, NFZ: za 47 dni, prywatnie: za 3 dni" z realnymi danymi
- Animowany flow: scan → auto-fill → thinking → results → NFZ/prywatni
- Attention heatmap jest wizualnie fascynujący
- Trendy: "wrzuć wyniki z marca, wrzuć z teraz — patrz jak kreatynina rośnie"

### Opus 4.7 Use (20%) — "Kreatywne użycie AI"
- NIE jako chatbot — jako warstwa inteligencji nad modelem ML
- **Vision/OCR**: skan kartki z wynikami + ekstrakcja norm laboratoryjnych
- **Tłumacz medyczny**: dynamiczne wyjaśnienia parametrów prostym językiem
- **Kontekst kombinacji**: rozumie że HGB↓ + Creatinine↑ razem = inna sytuacja
- **Analiza trendów**: porównuje 2+ zestawy wyników, interpretuje kierunek zmian
- **Dual output**: generuje inny tekst dla pacjenta vs lekarza (ten sam model, różne prompty)
- Dynamiczny interview (zamiast sztywnych reguł)
- "Second opinion" — Opus weryfikuje BERT, flaguje rozbieżności
- To jest unikalne: hybryda ML model + LLM multimodal, nie "kolejny wrapper na API"
- **Łącznie Opus jest używany na 6 sposobów**: Vision, NLG patient, NLG clinical, trend analysis, interview, verification

### Depth & Execution (20%) — "Czy to solidne?"
- Paper naukowy jako fundament (peer-reviewed methodology)
- Patient-level validation, cost-sensitive loss
- Attention-based interpretability (XAI)
- Dual mode (pacjent/klinicysta) — przemyślany UX, nie feature dla feature'u
- Integracja z publicznym API rządowym (NFZ) — realne dane, nie mock
- Trend analysis — klinicznie uzasadniony feature (lekarze patrzą na trendy)
- Open source, clean code, documented API
- Error handling, edge cases, loading states, fallbacks na każdym kroku

---

## Ryzyka i mitygacja

| Ryzyko | Prawdopodobieństwo | Mitygacja |
|--------|-------------------|-----------|
| Model nie działa na nowym serwerze | Średnie | Testuj deployment w dniu 1 |
| Google Places API limit | Niskie | Cache wyników, fallback na mock data |
| Opus API rate limit | Średnie | Cache wyjaśnień, fallback na template |
| Demo się zacina na żywo | Średnie | Backup video, pre-loaded scenarios |
| Frontend nie wygląda dobrze | Niskie | Użyj shadcn/ui + custom design system |
| OCR nie czyta kartki dobrze | Średnie | Podgląd "sprawdź i zatwierdź", manual fallback |
| Normy z kartki źle rozpoznane | Średnie | Fallback na domyślne lab_norms.json + walidacja |
| Camera API nie działa w przeglądarce | Niskie | Fallback na upload pliku (foto/PDF) |
| NFZ API nie odpowiada / wolne | Niskie | Cache danych, fallback na ostatni snapshot |
| Sędziowie pytają "czym to się różni od ChatGPT" | Wysokie | Przygotuj jasną odpowiedź (patrz niżej) |

---

## Odpowiedź na "czym to się różni od wrzucenia wyników do ChatGPT?"

To pytanie padnie. Przygotuj odpowiedź:

1. **Dedykowany model ML vs general LLM**: nasz BERT jest trenowany na danych klinicznych (MIMIC + Synthea, 260k encounters) z cost-sensitive focal loss — ma wymierną czułość 100% na SOR, kalibrację ECE < 0.01. ChatGPT nie ma walidacji klinicznej.

2. **Multi-label output**: nasz model daje 8 niezależnych prawdopodobieństw jednocześnie. LLM daje jedną odpowiedź tekstową bez kalibrowanych prawdopodobieństw.

3. **Interpretability**: attention visualization pokazuje DLACZEGO model podjął decyzję. ChatGPT to black box.

4. **Opus 4.7 NIE zastępuje modelu**: jest warstwą inteligencji NAD modelem — tłumaczy, weryfikuje, analizuje trendy. To hybryda, nie monolit.

5. **Realne dane**: NFZ API daje prawdziwe kolejki, nie "sugerujemy odwiedzić lekarza."

---

## Odpowiedź na "czy to nie niebezpieczne — pacjent sam się diagnozuje?"

1. **Dual mode**: tryb pacjenta nigdy nie pokazuje surowych prawdopodobieństw. Pokazuje "zalecamy konsultację nefrologiczną" — nie "92% nefrologia."

2. **Human-in-the-loop**: każdy ekran ma disclaimer. System sugeruje, nie diagnozuje.

3. **Lepsze niż status quo**: alternatywą jest pacjent, który googluje "wysoka kreatynina" i trafia na forum z nieprawdziwymi informacjami. Nasz system daje zweryfikowaną, kalibrowaną sugestię.

4. **Tryb kliniczny istnieje**: lekarz POZ może używać pełnego widoku do wsparcia decyzji.
