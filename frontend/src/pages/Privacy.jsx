import { LegalPage, Section, List, Fill } from "../components/marketing/LegalLayout";
import { SALES_EMAIL } from "../components/marketing/pricing";

/* NOT LEGAL ADVICE. A starting draft describing what the software actually
   collects and stores — not reviewed by a lawyer. The section on other
   people's data (section 3) is the one that carries real regulatory risk:
   PetroLead processes personal data about people who never signed up, which
   is exactly what the GDPR and similar laws are about. Have this reviewed
   before launch, and keep it truthful as the code changes. */

export default function Privacy() {
  return (
    <LegalPage
      title="Privacy Policy"
      updated={<Fill>DATE</Fill>}
      intro="What PetroLead collects, why, and what you can ask us to do about it."
    >
      <Section title="1. Who controls your data">
        <p>
          <Fill>LEGAL ENTITY NAME</Fill> of <Fill>REGISTERED ADDRESS</Fill> is the data controller
          for the information described here. Contact us at{" "}
          <a className="text-brand-600 hover:underline" href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>
          {" "}about anything on this page, including to exercise the rights in section 7.
          {" "}<Fill>IF YOU HAVE A DATA PROTECTION OFFICER OR AN EU/UK REPRESENTATIVE, NAME THEM HERE</Fill>
        </p>
      </Section>

      <Section title="2. What we collect about you, our customer">
        <List
          items={[
            "Account: your email address and a hashed password (we never store the password itself).",
            "Subscription: your plan, credit balance, credit history and paid period.",
            "Payments: the order reference, plan, amount, coin and network, the receiving address, and any blockchain transaction ID you provide. We do not hold your wallet, keys or any card details.",
            "Usage: the searches and lookups you run, the companies and contacts you save, and your scheduled searches.",
            "Technical: server logs including IP address, request paths and timestamps, kept for security and debugging.",
          ]}
        />
        <p>
          We use this to provide the service, count credits correctly, confirm payments, keep
          accounts secure, and contact you about your account. We do not sell it, and we do not use
          it for advertising.
        </p>
      </Section>

      <Section title="3. Data about other people">
        <p>
          PetroLead finds business contact details — names, job titles, company email addresses and
          phone numbers — for people who have not signed up to our service. This is personal data
          and we treat it as such.
        </p>
        <List
          items={[
            "Sources: publicly accessible company websites and public search results, plus third-party business-data providers. We do not access login-gated pages or buy consumer data.",
            "Scope: business contact details in a professional context. We do not seek personal addresses, personal phone numbers or any special-category data.",
            "Lawful basis: legitimate interests — connecting businesses with business suppliers and customers — balanced against the privacy of the people concerned.",
            "Retention: results are stored in the account of the customer who saved them, and deleted when they delete them or close their account.",
          ]}
        />
        <p>
          <strong className="font-semibold text-ink-300">
            If you are one of these people and want your details removed:
          </strong>{" "}
          email{" "}
          <a className="text-brand-600 hover:underline" href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>{" "}
          and we will delete them from our systems and, where we can, prevent them being
          rediscovered. You do not need an account, and we will not ask you to create one.
        </p>
        <p>
          Our customers are separately responsible for how they use contact details they find here,
          including telling people where they got them.
        </p>
      </Section>

      <Section title="4. Cookies and local storage">
        <p>
          We use no advertising or analytics trackers. Your browser stores your login token and a
          few interface preferences locally so you stay signed in; clearing your browser storage
          signs you out. That is all.
        </p>
      </Section>

      <Section title="5. Who else processes it">
        <p>These providers handle data on our behalf, under contract:</p>
        <List
          items={[
            <>
              <Fill>HOSTING PROVIDER</Fill> — application hosting and the database.
            </>,
            <>
              <Fill>SEARCH PROVIDER</Fill> and <Fill>CONTACT-DATA PROVIDER</Fill> — receive search
              terms and company domains to return results.
            </>,
            <>
              <Fill>EMAIL PROVIDER, IF SMTP IS CONFIGURED</Fill> — delivers account and payment
              emails.
            </>,
            "CoinGecko — provides exchange rates. It receives no personal data.",
          ]}
        />
        <p>
          Blockchain payments are not private: transactions on Bitcoin and TRON are public,
          permanent and outside our control.
        </p>
        <p>
          Some providers are outside your country. Where data leaves the UK or EEA we rely on{" "}
          <Fill>TRANSFER MECHANISM — e.g. standard contractual clauses</Fill>.
        </p>
      </Section>

      <Section title="6. How long we keep it">
        <List
          items={[
            "Account and saved data: until you delete it or close your account.",
            "Payment and credit records: kept after closure where tax or accounting law requires it — typically several years.",
            "Server logs: a short rolling window for security and debugging.",
          ]}
        />
      </Section>

      <Section title="7. Your rights">
        <p>
          Depending on where you live, you can ask us to give you a copy of your data, correct it,
          delete it, restrict or object to how we use it, or send it to another provider. Email{" "}
          <a className="text-brand-600 hover:underline" href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>
          {" "}and we will respond within <Fill>30</Fill> days. These rights apply whether or not you
          are a customer.
        </p>
        <p>
          If you think we have handled your data badly, please tell us first — but you can also
          complain to your data protection authority, which in the UK is the Information
          Commissioner&apos;s Office.
        </p>
      </Section>

      <Section title="8. Security">
        <p>
          Passwords are hashed with bcrypt, sessions use signed tokens, traffic is served over
          HTTPS, and each account can only ever read its own saved data. No system is perfectly
          secure; if a breach affects you we will tell you and the relevant authority as the law
          requires.
        </p>
      </Section>

      <Section title="9. Children">
        <p>
          PetroLead is a business tool and is not intended for anyone under 18. We do not knowingly
          collect data about children.
        </p>
      </Section>

      <Section title="10. Changes">
        <p>
          We will update this page when what we do changes, and change the date at the top. Material
          changes are announced to account holders by email.
        </p>
      </Section>
    </LegalPage>
  );
}
