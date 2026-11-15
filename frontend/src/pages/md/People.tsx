// MD · People: everyone who clocks in (deactivated people too: their history is kept).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMdPeople, type MdPerson } from "../../api";
import { initials } from "../../format";
import { ChevronRight } from "../../ui/icons";
import { Pill } from "../../ui/Pill";
import { MdShell } from "./Shell";

export function MdPeople() {
  const [people, setPeople] = useState<MdPerson[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getMdPeople().then((d) => setPeople(d.people)).catch((e) => setError(e.message)); }, []);
  return (
    <MdShell title="People" subtitle="Open a person to see their days, month by month.">
      {error && <p className="error-text" role="alert">{error}</p>}
      {people && (
        <div className="group" style={{ maxWidth: 760 }}>
          {people.map((p) => (
            <Link key={p.id} to={`/md/people/${p.id}`} className="row row-link" style={{ minHeight: 56 }}>
              <span className="person-initials" aria-hidden="true">{initials(p.name)}</span>
              <span className="row-body">
                <span className="two-line">
                  <span style={{ fontWeight: 600 }}>{p.name}</span>
                  <span className="sub-note">{p.role === "manager" ? "Manager" : "Worker"}
                    {p.phone_registered ? ` · phone registered ${p.phone_registered}` : " · no phone yet"}</span>
                </span>
                <span className="row-right">
                  {!p.active && <Pill tone="wait">Deactivated</Pill>}
                  <span className="row-chevron"><ChevronRight /></span>
                </span>
              </span>
            </Link>
          ))}
          {!people.length && <p className="empty-note">Nobody added yet.</p>}
        </div>
      )}
    </MdShell>
  );
}
