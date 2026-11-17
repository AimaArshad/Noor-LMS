import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getErrorMessage, getStatus } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import type { AnswerInput } from "@/features/quizzes/api";
import { QuizTimer } from "@/features/quizzes/components/QuizTimer";
import { useSubmitQuiz } from "@/features/quizzes/hooks";
import { cn } from "@/lib/utils";
import type { AttemptResult, StudentQuestion, StudentQuiz } from "@/types";

export interface QuizSession {
  attemptId: string;
  expiresAt: string | null;
  skewMs: number;
  quiz: StudentQuiz;
}

interface Answer {
  optionId?: string;
  text?: string;
}
type Answers = Record<string, Answer>;

const storageKey = (attemptId: string) => `noorlms.quiz.${attemptId}`;

function loadAnswers(attemptId: string): Answers {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(storageKey(attemptId)) ?? "null");
    return parsed && typeof parsed === "object" ? (parsed as Answers) : {};
  } catch {
    return {};
  }
}

function isAnswered(question: StudentQuestion, answer: Answer | undefined): boolean {
  if (!answer) return false;
  return question.type === "short_answer" ? Boolean(answer.text?.trim()) : Boolean(answer.optionId);
}

function toPayload(questions: StudentQuestion[], answers: Answers): AnswerInput[] {
  return questions.flatMap((q): AnswerInput[] => {
    const answer = answers[q.id];
    if (!isAnswered(q, answer)) return [];
    return q.type === "short_answer"
      ? [{ question_id: q.id, answer_text: answer?.text?.trim() }]
      : [{ question_id: q.id, selected_option_id: answer?.optionId }];
  });
}

function QuestionView({
  question,
  number,
  total,
  answer,
  disabled,
  onChange,
}: {
  question: StudentQuestion;
  number: number;
  total: number;
  answer: Answer | undefined;
  disabled: boolean;
  onChange: (next: Answer) => void;
}) {
  return (
    <fieldset
      disabled={disabled}
      className="animate-enter space-y-4 rounded-xl border bg-card p-5 shadow-sm sm:p-6"
    >
      <legend className="space-y-1">
        <span className="block text-sm text-muted-foreground">
          Question {number} of {total} · {question.points} point{question.points === 1 ? "" : "s"}
        </span>
        <span className="block whitespace-pre-wrap break-words text-lg font-medium">{question.prompt}</span>
      </legend>

      {question.type === "short_answer" ? (
        <Textarea
          aria-label={`Your answer to question ${number}`}
          rows={4}
          maxLength={5000}
          value={answer?.text ?? ""}
          onChange={(e) => onChange({ text: e.target.value })}
        />
      ) : (
        <div className="space-y-2">
          {question.options.map((option) => (
            <label
              key={option.id}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 text-sm transition-[background-color,border-color,box-shadow] duration-150 hover:border-primary/40 hover:bg-accent/60 focus-within:ring-2 focus-within:ring-ring",
                answer?.optionId === option.id && "border-primary bg-primary/10 shadow-sm ring-1 ring-primary/30",
              )}
            >
              <input
                type="radio"
                name={`question-${question.id}`}
                className="mt-0.5 h-4 w-4 accent-primary"
                checked={answer?.optionId === option.id}
                onChange={() => onChange({ optionId: option.id })}
              />
              <span className="break-words">{option.text}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

interface QuizTakerProps {
  session: QuizSession;
  onSubmitted: (result: AttemptResult) => void;
  /** Leave the attempt screen without a result (e.g. the time limit passed). */
  onAbort: () => void;
}

export function QuizTaker({ session, onSubmitted, onAbort }: QuizTakerProps) {
  const { quiz, attemptId } = session;
  const questions = quiz.questions;
  const { mutate, isPending, isError, error } = useSubmitQuiz(quiz.id);

  const [answers, setAnswers] = useState<Answers>(() => loadAnswers(attemptId));
  const [index, setIndex] = useState(0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [unanswered, setUnanswered] = useState(0);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const answersRef = useRef(answers);
  answersRef.current = answers;
  const sentRef = useRef(false);

  // Keep answers across a page refresh (the open attempt resumes through /start).
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey(attemptId), JSON.stringify(answers));
    } catch {
      /* storage blocked: answers just will not survive a reload */
    }
  }, [answers, attemptId]);

  // Warn before leaving the page while the attempt is running.
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (sentRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  const send = useCallback(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    mutate(toPayload(questions, answersRef.current), {
      onSuccess: (result) => {
        try {
          sessionStorage.removeItem(storageKey(attemptId));
        } catch {
          /* ignore */
        }
        onSubmitted(result);
      },
      onError: () => {
        sentRef.current = false;
      },
    });
  }, [mutate, questions, attemptId, onSubmitted]);

  function onSubmitClick() {
    const missing = questions.filter((q) => !isAnswered(q, answers[q.id])).length;
    if (missing > 0) {
      setUnanswered(missing);
      setConfirmOpen(true);
      return;
    }
    send();
  }

  const question = questions[index];
  if (!question) {
    return <p className="text-muted-foreground">This quiz has no questions.</p>;
  }
  const answeredCount = questions.filter((q) => isAnswered(q, answers[q.id])).length;
  const timeIsUp = isError && getStatus(error) === 409;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4 shadow-sm">
        <div>
          <h2 className="text-lg font-semibold">{quiz.title}</h2>
          <p className="text-sm text-muted-foreground">
            {answeredCount} of {questions.length} answered
          </p>
          <div
            role="progressbar"
            aria-label="Questions answered"
            aria-valuemin={0}
            aria-valuemax={questions.length}
            aria-valuenow={answeredCount}
            className="mt-2 h-2 w-40 overflow-hidden rounded-full bg-muted"
          >
            <div
              className="h-full rounded-full bg-brand transition-[width] duration-300"
              style={{ width: `${(answeredCount / questions.length) * 100}%` }}
            />
          </div>
        </div>
        {session.expiresAt ? (
          <QuizTimer expiresAt={session.expiresAt} skewMs={session.skewMs} onExpire={send} />
        ) : (
          <p className="text-sm text-muted-foreground">No time limit</p>
        )}
      </div>

      <ErrorAlert message={isError ? getErrorMessage(error) : null} />
      {timeIsUp ? (
        <Button variant="outline" onClick={onAbort}>
          Back to the quiz page
        </Button>
      ) : null}

      <div className="grid gap-6 md:grid-cols-[1fr_14rem]">
        <div className="space-y-6">
          <QuestionView
            key={question.id}
            question={question}
            number={index + 1}
            total={questions.length}
            answer={answers[question.id]}
            disabled={isPending}
            onChange={(next) => setAnswers((current) => ({ ...current, [question.id]: next }))}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button type="button" variant="outline" disabled={index === 0} onClick={() => setIndex(index - 1)}>
              <ChevronLeft aria-hidden="true" />
              Previous
            </Button>
            {index < questions.length - 1 ? (
              <Button type="button" variant="outline" onClick={() => setIndex(index + 1)}>
                Next
                <ChevronRight aria-hidden="true" />
              </Button>
            ) : (
              <Button type="button" disabled={isPending} onClick={onSubmitClick}>
                {isPending ? "Submitting…" : "Submit quiz"}
              </Button>
            )}
          </div>
        </div>

        <nav aria-label="Question navigator" className="space-y-3">
          <ol className="grid grid-cols-5 gap-2 md:grid-cols-4">
            {questions.map((q, i) => {
              const answered = isAnswered(q, answers[q.id]);
              return (
                <li key={q.id}>
                  <button
                    type="button"
                    aria-label={`Question ${i + 1}, ${answered ? "answered" : "not answered"}`}
                    aria-current={i === index ? "step" : undefined}
                    onClick={() => setIndex(i)}
                    className={cn(
                      "h-10 w-full rounded-lg border bg-card text-sm font-medium transition-[transform,background-color,border-color,box-shadow] duration-150 hover:border-primary/50 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      answered ? "border-primary/50 bg-primary/10 text-primary" : "text-muted-foreground",
                      i === index && "ring-2 ring-primary ring-offset-1",
                    )}
                  >
                    {i + 1}
                  </button>
                </li>
              );
            })}
          </ol>
          <Button type="button" className="w-full" disabled={isPending} onClick={onSubmitClick}>
            {isPending ? "Submitting…" : "Submit quiz"}
          </Button>
        </nav>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent
          className="max-w-md"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancelRef.current?.focus();
          }}
        >
          <DialogHeader>
            <DialogTitle>Submit without answering everything?</DialogTitle>
            <DialogDescription>
              You have {unanswered} unanswered question{unanswered === 1 ? "" : "s"}. Submit anyway?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button ref={cancelRef} type="button" variant="outline" onClick={() => setConfirmOpen(false)}>
              Keep working
            </Button>
            <Button
              type="button"
              onClick={() => {
                setConfirmOpen(false);
                send();
              }}
            >
              Submit anyway
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
