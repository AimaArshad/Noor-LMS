import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { ClassroomLayout } from "@/components/layout/ClassroomLayout";
import { AdminPage } from "@/pages/AdminPage";
import { LoginPage } from "@/pages/auth/LoginPage";
import { RegisterPage } from "@/pages/auth/RegisterPage";
import { ClassworkPage } from "@/pages/classroom/ClassworkPage";
import { PeoplePage } from "@/pages/classroom/PeoplePage";
import { StreamPage } from "@/pages/classroom/StreamPage";
import { ClassesPage } from "@/pages/ClassesPage";
import { HomePage } from "@/pages/HomePage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { TodoPage } from "@/pages/TodoPage";
import { GuestRoute } from "@/routes/GuestRoute";
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
                { path: "people", element: <PeoplePage /> },
                // later steps: classwork/assignments/:id, classwork/quizzes/:id, materials/:id ...
              ],
            },
            { path: "*", element: <NotFoundPage /> },
          ],
        },
      ],
    },
  ],
  // Opt into the v7 behaviours now: this is what React Router 7 will do by default.
  { future: { v7_relativeSplatPath: true } },
);
