import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { ClassroomLayout } from "@/components/layout/ClassroomLayout";
import { AdminPage } from "@/pages/AdminPage";
import { AssignmentPage } from "@/pages/classroom/AssignmentPage";
import { AudiobooksPage } from "@/pages/classroom/AudiobooksPage";
import { ClassworkPage } from "@/pages/classroom/ClassworkPage";
import { GradesPage } from "@/pages/classroom/GradesPage";
import { PeoplePage } from "@/pages/classroom/PeoplePage";
import { QuizBuilderPage } from "@/pages/classroom/QuizBuilderPage";
import { QuizPage } from "@/pages/classroom/QuizPage";
import { StreamPage } from "@/pages/classroom/StreamPage";
import { ClassesPage } from "@/pages/ClassesPage";
import { HomePage } from "@/pages/Home";
import { LoginPage } from "@/pages/Login";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RegisterPage } from "@/pages/Register";
import { TodoPage } from "@/pages/Todo";
import { GuestRoute } from "@/routes/GuestRoute";
import { ClassroomsRedirect } from "@/routes/ClassroomsRedirect";
import { MaterialRedirect } from "@/routes/MaterialRedirect";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { RoleRoute } from "@/routes/RoleRoute";

export const router = createBrowserRouter(
  [
    {
      element: <GuestRoute />,
      children: [
        { path: "/login", element: <LoginPage /> },
        { path: "/register", element: <RegisterPage /> },
      ],
    },
    {
      element: <ProtectedRoute />,
      children: [
        {
          element: <AppLayout />,
          children: [
            { index: true, element: <HomePage /> },
            { path: "todo", element: <TodoPage /> },
            { path: "classes", element: <ClassesPage /> },
            { path: "profile", element: <ProfilePage /> },
            {
              element: <RoleRoute roles={["admin"]} />,
              children: [{ path: "admin", element: <AdminPage /> }],
            },
            {
              path: "classes/:classroomId",
              element: <ClassroomLayout />,
              children: [
                { index: true, element: <StreamPage /> },
                { path: "classwork", element: <ClassworkPage /> },
                { path: "audiobooks", element: <AudiobooksPage /> },
                { path: "people", element: <PeoplePage /> },
                { path: "grades", element: <GradesPage /> },
                { path: "assignments/:assignmentId", element: <AssignmentPage /> },
                { path: "materials/:materialId", element: <MaterialRedirect /> },
                { path: "quizzes/new", element: <QuizBuilderPage /> },
                { path: "quizzes/:quizId", element: <QuizPage /> },
              ],
            },
            { path: "classrooms/:classroomId/*", element: <ClassroomsRedirect /> },
            { path: "*", element: <NotFoundPage /> },
          ],
        },
      ],
    },
  ],
  // Opt into the v7 behaviours now: this is what React Router 7 will do by default.
  { future: { v7_relativeSplatPath: true } },
);
