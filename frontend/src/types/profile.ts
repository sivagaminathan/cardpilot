export interface Profile {
  id: string;
  name: string;
  role: string;
  description: string;
}

export const DEMO_PROFILES: Profile[] = [
  {
    id: 'maya',
    name: 'Maya',
    role: 'The Optimizer',
    description: 'Holds 4 cards, focuses on maximizing dining and travel rewards',
  },
  {
    id: 'dev',
    name: 'Dev',
    role: 'The Benefit Tracker',
    description: 'Pays annual fees, tracks monthly credits and travel allowances',
  },
  {
    id: 'rivera',
    name: 'Prof. Rivera',
    role: 'Course Reviewer',
    description: 'Evaluates deterministic calculations, traces, and architecture',
  },
];
