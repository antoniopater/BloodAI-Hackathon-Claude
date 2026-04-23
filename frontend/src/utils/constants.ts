import type { LabParam, LabReferenceRange, TriageClass } from '../types/medical'

/**
 * Reference ranges (adult, general population).
 * Sources consolidated from standard lab panels; these are educational
 * defaults — the real backend `data/lab_norms.json` is the source of truth.
 */
export const LAB_REFERENCE: Record<LabParam, LabReferenceRange> = {
  HGB: {
    param: 'HGB',
    label: 'Hemoglobin',
    unit: 'g/dL',
    low: 12.0,
    high: 17.5,
    criticalLow: 7.0,
    criticalHigh: 20.0,
    description:
      'Protein in red blood cells that carries oxygen. Low values suggest anemia; very high values may suggest dehydration or polycythemia.',
  },
  CREATININE: {
    param: 'CREATININE',
    label: 'Creatinine',
    unit: 'mg/dL',
    low: 0.6,
    high: 1.3,
    criticalHigh: 4.0,
    description:
      'A waste product cleared by the kidneys. High values can signal reduced kidney function.',
  },
  PLT: {
    param: 'PLT',
    label: 'Platelets',
    unit: '10³/µL',
    low: 150,
    high: 400,
    criticalLow: 50,
    criticalHigh: 1000,
    description:
      'Small cells that help blood clot. Low counts can cause bleeding; very high counts may indicate inflammation or bone marrow disease.',
  },
  MCV: {
    param: 'MCV',
    label: 'Mean Corpuscular Volume',
    unit: 'fL',
    low: 80,
    high: 100,
    description:
      'Average size of red blood cells. Helps classify anemia (small, normal, or large cells).',
  },
  WBC: {
    param: 'WBC',
    label: 'White Blood Cells',
    unit: '10³/µL',
    low: 4.0,
    high: 11.0,
    criticalLow: 1.0,
    criticalHigh: 30.0,
    description:
      'Immune cells. High values often indicate infection or inflammation; very low values mean reduced immunity.',
  },
  ALT: {
    param: 'ALT',
    label: 'ALT (liver enzyme)',
    unit: 'U/L',
    low: 7,
    high: 56,
    criticalHigh: 500,
    description:
      'Liver enzyme released when liver cells are damaged. High values suggest liver stress or injury.',
  },
  AST: {
    param: 'AST',
    label: 'AST (liver enzyme)',
    unit: 'U/L',
    low: 10,
    high: 40,
    criticalHigh: 500,
    description:
      'Enzyme found in the liver and muscle. Elevated together with ALT points to liver injury.',
  },
  UREA: {
    param: 'UREA',
    label: 'Urea (BUN)',
    unit: 'mg/dL',
    low: 7,
    high: 20,
    criticalHigh: 100,
    description:
      'Waste product filtered by the kidneys. High values may mean kidney issues or dehydration.',
  },
}

/** Plain-language names for triage classes (shown to patients). */
export const TRIAGE_LABELS: Record<TriageClass, { en: string; patient: string; emoji: string }> = {
  POZ: { en: 'Primary care (GP)', patient: 'Family doctor', emoji: '👨‍⚕️' },
  Gastroenterology: { en: 'Gastroenterology', patient: 'Stomach & gut specialist', emoji: '🫃' },
  Hematology: { en: 'Hematology', patient: 'Blood specialist', emoji: '🩸' },
  Nephrology: { en: 'Nephrology', patient: 'Kidney specialist', emoji: '🫘' },
  ER: { en: 'Emergency Department', patient: 'Go to the ER — urgent', emoji: '🚨' },
  Cardiology: { en: 'Cardiology', patient: 'Heart specialist', emoji: '❤️' },
  Pulmonology: { en: 'Pulmonology', patient: 'Lung specialist', emoji: '🫁' },
  Hepatology: { en: 'Hepatology', patient: 'Liver specialist', emoji: '🟤' },
}

/** Suggested follow-up questions per triage class (adaptive interview fallback). */
export const DEFAULT_FOLLOWUP_QUESTIONS: Partial<Record<TriageClass, string[]>> = {
  Nephrology: [
    'Have you noticed changes in how often you urinate?',
    'Any swelling in your legs, ankles, or around the eyes?',
    'Is there foam in your urine, or a change in its color?',
  ],
  Hematology: [
    'Have you been unusually tired or short of breath?',
    'Any unexplained bruising or bleeding gums?',
    'Any night sweats or unexpected weight loss?',
  ],
  Hepatology: [
    'Any yellowing of the skin or the whites of the eyes?',
    'Pain or pressure on the right side under the ribs?',
    'Have you started any new medication or supplement?',
  ],
  Cardiology: [
    'Any chest pain, pressure, or tightness?',
    'Do you get short of breath on light activity?',
    'Swelling in the legs or ankles by evening?',
  ],
  Pulmonology: [
    'Do you have a persistent cough? For how long?',
    'Have you noticed shortness of breath?',
    'Any smoking history or exposure to dust?',
  ],
  Gastroenterology: [
    'Any changes in appetite or bowel habits?',
    'Pain or discomfort after meals?',
    'Blood in stool, or unusually dark stools?',
  ],
  ER: [
    'Are you experiencing severe pain, fainting, or trouble breathing?',
    'When did the symptoms start?',
    'Are you alone, or is someone with you?',
  ],
}

/** Polish provinces (NFZ API uses numeric codes). */
export const PL_PROVINCES: Array<{ code: string; name: string }> = [
  { code: '01', name: 'Dolnośląskie' },
  { code: '02', name: 'Kujawsko-Pomorskie' },
  { code: '03', name: 'Lubelskie' },
  { code: '04', name: 'Lubuskie' },
  { code: '05', name: 'Łódzkie' },
  { code: '06', name: 'Małopolskie' },
  { code: '07', name: 'Mazowieckie' },
  { code: '08', name: 'Opolskie' },
  { code: '09', name: 'Podkarpackie' },
  { code: '10', name: 'Podlaskie' },
  { code: '11', name: 'Pomorskie' },
  { code: '12', name: 'Śląskie' },
  { code: '13', name: 'Świętokrzyskie' },
  { code: '14', name: 'Warmińsko-Mazurskie' },
  { code: '15', name: 'Wielkopolskie' },
  { code: '16', name: 'Zachodniopomorskie' },
]

/** Map triage class -> NFZ "benefit" query string (Polish). */
export const TRIAGE_TO_NFZ_BENEFIT: Record<TriageClass, string> = {
  POZ: 'PORADNIA LEKARZA POZ',
  Gastroenterology: 'PORADNIA GASTROENTEROLOGICZNA',
  Hematology: 'PORADNIA HEMATOLOGICZNA',
  Nephrology: 'PORADNIA NEFROLOGICZNA',
  ER: 'SZPITALNY ODDZIAŁ RATUNKOWY',
  Cardiology: 'PORADNIA KARDIOLOGICZNA',
  Pulmonology: 'PORADNIA CHORÓB PŁUC',
  Hepatology: 'PORADNIA HEPATOLOGICZNA',
}

export const MEDICAL_DISCLAIMER =
  'BloodAI is an educational tool. It does not replace consultation with a qualified physician. Always consult your doctor before making medical decisions.'

export const TOTAL_STEPS = 4
