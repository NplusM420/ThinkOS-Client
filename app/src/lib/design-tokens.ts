/**
 * Design tokens for consistent styling across the app.
 * Single source of truth for glassmorphism, actions, and chip styles.
 */

// Glassmorphism base (used on cards, messages, panels)
export const glass = {
  base: "bg-white/70 dark:bg-white/5 backdrop-blur-md border border-white/60 dark:border-white/10 shadow-sm shadow-black/5 dark:shadow-black/20",
  hover:
    "hover:shadow-lg hover:shadow-black/10 dark:hover:shadow-black/30 hover:scale-[1.01] hover:-translate-y-0.5 transition-all duration-200",
};

// Action buttons that fade in on hover
export const actions = {
  container: "opacity-0 group-hover:opacity-100 transition-opacity duration-200",
  button: "h-7 w-7 text-muted-foreground hover:text-primary",
};

// Prompt chips (quick prompts, follow-ups)
export const chips = {
  base: "px-2.5 py-1 text-xs rounded-full transition-colors",
  glass:
    "bg-white/70 dark:bg-white/5 border border-white/60 dark:border-white/10 hover:bg-primary/10",
  primary: "bg-primary/10 text-primary hover:bg-primary/20",
};

// Full-screen editor (NoteEditor)
export const editor = {
  container: "fixed inset-0 z-50 bg-background",
  toolbar: "inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-muted/50 border border-border/50",
  content: "max-w-3xl mx-auto px-6 py-8",
  title: "w-full text-3xl font-semibold bg-transparent border-none outline-none placeholder:text-muted-foreground/50",
  actionBar: "flex items-center justify-end gap-4 px-6 py-4 border-t border-border/30",
  actionBarWarning: "bg-amber-500/10 border-t-amber-500/30",
};
