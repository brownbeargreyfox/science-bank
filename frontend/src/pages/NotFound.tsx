import { Link } from "react-router";
import { PageHeader } from "../components/ui";

export default function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" lead="The address doesn’t match any page in Science Bank." />
      <Link to="/" className="btn">
        Go to Home
      </Link>
    </>
  );
}
