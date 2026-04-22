---
name: bloodai-day3-opus
description: "Dzień 3 hackathonu BloodAI: integracja Opus 4.7 — skan kamerą/PDF, wyjaśnienia kontekstowe, second opinion, inteligentny interview. To kluczowy dzień na punkty za 'Opus 4.7 Use'."
---

# Dzień 3: Opus 4.7 Integration + Skan

## Cel dnia
Na koniec dnia Opus 4.7 jest używany na minimum 4 sposoby: (1) Vision OCR skanu kartki, (2) tłumaczenie wyników, (3) analiza kontekstu/kombinacji, (4) second opinion nad BERT. To jest dzień, który wygrywa kategorię "Opus 4.7 Use (20%)".

## Checklist zadań

### Blok 1: Camera/PDF Scan — OCR wyników (3-4h) ⭐ PRIORYTET
- [ ] Frontend: komponent upload (drag & drop + camera input)
```html
<input type="file" accept="image/*,application/pdf" capture="environment" />
```
- [ ] Backend endpoint `POST /scan`:
  - Przyjmuje: base64 image lub PDF
  - Wysyła do Opus 4.7 z promptem:

```
Prompt do OCR:
"Jesteś ekspertem od odczytywania wyników badań laboratoryjnych.
Na zdjęciu/PDF jest kartka z wynikami badań krwi.

Wyodrębnij:
1. Każdy parametr laboratoryjny: nazwa, wartość, jednostka
2. Normy referencyjne podane na kartce (jeśli widoczne)
3. Dane pacjenta: wiek, płeć (jeśli widoczne)
4. Nazwa laboratorium (jeśli widoczna)

Odpowiedz TYLKO w JSON:
{
  "patient": {"age": null, "sex": null},
  "lab_name": null,
  "parameters": [
    {
      "name": "HGB",
      "value": 14.2,
      "unit": "g/dL",
      "reference_low": 12.0,
      "reference_high": 17.5,
      "source": "from_sheet"
    }
  ],
  "confidence": "high|medium|low",
  "notes": "any issues with readability"
}

Jeśli nie jesteś pewien wartości — ustaw confidence na 'low' i dodaj notatkę.
Nie zgaduj — lepiej pominąć niż podać złą wartość."
```

- [ ] Frontend: podgląd "Rozpoznaliśmy te wartości — sprawdź i zatwierdź"
  - Tabela: parametr | rozpoznana wartość | norma z kartki | norma domyślna | status
  - Edytowalne pola (użytkownik może poprawić)
  - Przycisk "Zatwierdź i analizuj"
- [ ] Fallback: jeśli OCR confidence = "low" → podświetl na żółto, poproś o weryfikację
- [ ] Fallback: jeśli normy nieczytelne → użyj domyślnych z lab_norms.json, pokaż info "normy domyślne"
- [ ] Obsługa PDF: Opus 4.7 jako document input (base64)

### Blok 2: Kontekstowe wyjaśnienia — podsumowanie (1-2h)
- [ ] Backend endpoint `POST /explain`:
  - Input: wyniki triażu + attention + wartości lab + demographics
  - Dwa tryby promptu:

```
Prompt tryb pacjenta:
"Na podstawie wyników badań krwi pacjenta ({wiek} lat, {płeć}):
{lista parametrów z wartościami i statusem}

Model AI wskazał następujące specjalizacje:
{lista specjalizacji z flagami}

Wyjaśnij wyniki prostym językiem (max 150 słów):
- Co jest nie tak (bez straszenia)
- Dlaczego te specjalizacje
- Co pacjent powinien zrobić dalej
Nie diagnozuj. Zawsze zalecaj konsultację lekarską."

Prompt tryb kliniczny:
"Wyniki triażu BERT multi-label dla pacjenta ({wiek}, {płeć}):
{parametry z kwantylami i wartościami attention}
Prawdopodobieństwa: {lista 8 klas z wartościami}
Attention top-3: {tokeny z najwyższą attention}

Podaj krótką interpretację kliniczną (max 100 słów):
- Dominujące sygnały w attention
- Sugestia co do pilności (stabilny/pilny/nagły)
- Ewentualne dual review jeśli >1 specjalizacja >0.5"
```

### Blok 3: Second Opinion — Opus weryfikuje BERT (1h)
- [ ] Backend: po predykcji BERT, opcjonalnie wyślij ten sam case do Opus 4.7:

```
Prompt second opinion:
"Pacjent {wiek} lat, {płeć}. Wyniki badań:
{parametry z wartościami}

Model ML BERT zasugerował:
{lista specjalizacji z prawdopodobieństwami}

Czy zgadzasz się z tym routingiem?
Odpowiedz TYLKO w JSON:
{
  "agree": true/false,
  "disagreements": [
    {"class": "...", "bert_prob": 0.xx, "your_assessment": "...", "reason": "..."}
  ],
  "additional_concerns": "...",
  "confidence": "high|medium|low"
}
Nie zgaduj — jeśli nie masz wystarczających danych, powiedz."
```

- [ ] Frontend: jeśli Opus się nie zgadza → pokaż alert "Model AI i ekspert AI mają różne opinie — skonsultuj z lekarzem"
- [ ] To jest potężny argument na demo: "nasz system ma wbudowaną weryfikację"

### Blok 4: Inteligentny Interview (1h)
- [ ] Zamiast sztywnego banku pytań, Opus generuje pytania dynamicznie:

```
Prompt interview:
"Pacjent {wiek} lat, {płeć}. Parametr {nazwa} = {wartość} (norma: {low}-{high}).
Inne wyniki: {kontekst}
Wygeneruj JEDNO krótkie pytanie follow-up po polsku, które pomoże w triażu.
Odpowiedz TYLKO: {"question": "...", "token_yes": "...", "token_no": "..."}"
```

- [ ] Max 2-3 pytania na sesję
- [ ] Odpowiedź wpływa na re-predict (dodaj token do sekwencji)

### Blok 5: Raport PDF (1h — opcjonalne)
- [ ] Generuj PDF z podsumowaniem: dane pacjenta, wyniki, triage, attention, wyjaśnienie
- [ ] Do wydruku / do lekarza
- [ ] Disclaimer na każdej stronie

## Self-assessment na koniec dnia

| Pytanie | Score |
|---------|-------|
| Czy skan kamerą/PDF rozpoznaje wyniki poprawnie? | /5 |
| Czy normy z kartki są odczytywane (lub fallback działa)? | /5 |
| Czy wyjaśnienie Opus jest zrozumiałe i trafne? | /5 |
| Czy second opinion działa i pokazuje rozbieżności? | /5 |
| Ile sposobów użycia Opus 4.7 masz? (cel: min 4) | /5 |

**Policz sposoby użycia Opus 4.7:**
1. ☐ Vision/OCR (skan kartki)
2. ☐ Tłumacz parametrów (prostym językiem)
3. ☐ Wyjaśnienie kontekstowe (podsumowanie)
4. ☐ Second opinion (weryfikacja BERT)
5. ☐ Inteligentny interview (dynamiczne pytania)
6. ☐ Analiza trendów (dzień 4)

**6/6** = sędziowie będą pod wrażeniem
**4-5** = solidnie
**<4** = za mało — sędziowie ocenią jako "basic integration"

## Fallback
- Skan: jeśli OCR kuleje → skup się na PDF (bardziej czytelny niż zdjęcie)
- Second opinion: jeśli nie zdążysz → pomiń, nie jest must-have
- Raport PDF: opcjonalny, nice-to-have
- NIGDY nie rezygnuj z tłumacza parametrów — to core feature
