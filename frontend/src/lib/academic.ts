export const GRADES = [6, 7, 8, 9, 10] as const;
export type Grade = (typeof GRADES)[number];

export const gradeLabel = (grade: number) => `Class ${grade}`;
