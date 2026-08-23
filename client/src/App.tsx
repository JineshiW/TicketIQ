import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { RecurringPatternsPage } from "@/pages/RecurringPatternsPage";
import { SubmitTicketPage } from "@/pages/SubmitTicketPage";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/submit" replace />} />
        <Route path="/submit" element={<SubmitTicketPage />} />
        <Route path="/patterns" element={<RecurringPatternsPage />} />
        <Route path="*" element={<Navigate to="/submit" replace />} />
      </Routes>
    </Layout>
  );
}
