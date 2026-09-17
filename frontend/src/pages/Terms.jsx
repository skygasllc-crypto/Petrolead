import { Link } from "react-router-dom";
import { LegalPage, Section, List, Fill } from "../components/marketing/LegalLayout";
import { SALES_EMAIL } from "../components/marketing/pricing";

/* NOT LEGAL ADVICE. This is a starting draft written to match what the
   software actually does — it has not been reviewed by a lawyer. Every
   <Fill> below is a real decision (legal entity, jurisdiction, refund
   policy) that only the operator can make, and they are highlighted on the
   page so an unfinished version can't ship unnoticed. Have a lawyer review
   this before taking money from the public. */

export default function Terms() {
  return (
    <LegalPage
      title="Terms of Service"
      updated={<Fill></Fill>20 October, 2026</Fill>}
      intro="These terms govern your use of PetroLead. By creating an account you agree to them."
    >
      <Section title="1. Who we are">
        <p>
          PetroLead (&quot;we&quot;, &quot;us&quot;) is operated by <Fill>PETROL INVESTMENT</Fill>,
          registered in <Fill>Switzerland</Fill>
          {" "}under company number <Fill>Sw-00896</Fill>. You can
          reach us at <a className="text-brand-600 hover:underline" href={`mailto:${SALES_EMAIL}`}>{SALES_EMAIL}</a>.
        </p>
      </Section>

      <Section title="2. What the service does">
        <p>
          PetroLead finds companies in the petroleum and energy trade and business contact details
          for reaching them, using publicly available sources and third-party data providers. It is
          a business tool sold to businesses.
        </p>
        <p>
          We do not guarantee that any address we return is accurate, current, deliverable, or that
          anyone will reply to it. Contact data changes constantly and some of it will be wrong.
          Verification results are a best-effort signal, not a promise.
        </p>
      </Section>

      <Section title="3. Your account">
        <List
          items={[
            "You must be at least 18 and using the service for business purposes.",
            "You are responsible for everything done under your account, and for keeping your password secret.",
            "One account is for one organisation. Don't share credentials outside it.",
            "Tell us promptly if you believe your account has been accessed by someone else.",
          ]}
        />
      </Section>

      <Section title="4. Plans and email credits">
        <p>
          Each plan includes a monthly allowance of email credits. One credit is used each time we
          find a business email for you — from a LinkedIn profile link, a name and company, a line
          in a bulk lookup, or a result in a company search. Lookups and results that come back
          without a business email do not use a credit.
        </p>
        <List
          items={[
            "Unused credits roll over while your subscription is active.",
            "Plans also cap how many company searches you may run per day and how many results each returns.",
            "Credits have no cash value and cannot be transferred or refunded for cash.",
            "If your paid period ends, the tools stop until you renew; your saved data stays.",
          ]}
        />
        <p>
          We may change plan prices, allowances or how credits are counted. If a change affects a
          period you have already paid for, we will tell you before it takes effect.
        </p>
      </Section>

      <Section title="5. Payment in cryptocurrency">
        <p>
          Plans are paid in Bitcoin, Tether (USDT on the TRON network) or TRON. There is no card
          payment and no payment processor: you send the amount shown to the address shown, tell us
          you have paid, and we confirm it by hand against a public block explorer. Your plan starts
          when we confirm it, not when you click the button.
        </p>
        <List
          items={[
            "BTC and TRX amounts are quoted from a live exchange rate that is held for a limited time. If you pay after the quote expires, send the amount shown at the time you paid — we check the amount that actually arrived.",
            "Send the exact coin on the exact network shown. Coins sent on the wrong network, or to the wrong address, are permanently lost and we cannot recover or refund them.",
            "We may reject a payment we cannot find on the blockchain, and will tell you why.",
            "Blockchain transactions are public and permanent. We store the reference, amount and any transaction ID you give us.",
          ]}
        />
        <p>
          Refunds: <Fill>STATE YOUR REFUND POLICY — e.g. paid periods are non-refundable once the
          plan is activated, except where consumer law requires otherwise</Fill>. Nothing here
          removes rights you have under the law of your country.
        </p>
      </Section>

      <Section title="6. How you may use the data">
        <p>
          You are responsible for what you do with contact details you find here. Marketing and
          outreach law applies to you, not to us — including the GDPR and ePrivacy rules in Europe,
          the UK&apos;s PECR, CAN-SPAM in the United States, and their equivalents elsewhere.
        </p>
        <p>You agree not to:</p>
        <List
          items={[
            "Send unsolicited bulk messages, or contact anyone who has asked you to stop.",
            "Resell, republish or redistribute data obtained through PetroLead, or use it to build a competing database.",
            "Use the service to harass, defraud or profile individuals, or for consumer marketing.",
            "Scrape, copy or reverse-engineer the service, or circumvent its rate limits, credits or plan restrictions.",
            "Share your account with people outside your organisation.",
          ]}
        />
        <p>
          We may suspend or close an account that breaks these rules, without refunding the
          remaining period.
        </p>
      </Section>

      <Section title="7. Third-party sources">
        <p>
          Some results come from third-party search and contact-data providers, each with their own
          terms. We may change or remove a source at any time, which can change the results you get.
        </p>
      </Section>

      <Section title="8. Availability">
        <p>
          We aim to keep PetroLead running but do not promise uninterrupted service. We may change,
          suspend or discontinue features, and we carry out maintenance that can involve downtime.
          The service is provided &quot;as is&quot;, without warranties of any kind to the extent the
          law allows.
        </p>
      </Section>

      <Section title="9. Limitation of liability">
        <p>
          To the fullest extent permitted by law, we are not liable for lost profits, lost business,
          lost or inaccurate data, or any indirect or consequential loss. Our total liability to you
          for any claim is limited to the amount you paid us in the <Fill>12</Fill> months before the
          claim arose.
        </p>
        <p>
          Nothing in these terms limits liability for death or personal injury caused by negligence,
          for fraud, or for anything else that cannot lawfully be limited.
        </p>
      </Section>

      <Section title="10. Ending your subscription">
        <p>
          Nothing renews automatically: a plan simply ends when its paid period does. You can stop
          using the service at any time. You may ask us to delete your account and data as described
          in our <Link className="text-brand-600 hover:underline" to="/privacy">Privacy Policy</Link>.
        </p>
      </Section>

      <Section title="11. Changes to these terms">
        <p>
          We may update these terms. The date at the top shows when they last changed, and we will
          tell account holders about material changes by email before they take effect.
        </p>
      </Section>

      <Section title="12. Governing law">
        <p>
          These terms are governed by the law of <Fill>JURISDICTION</Fill>, and disputes will be
          heard in the courts of <Fill>JURISDICTION</Fill>.
        </p>
      </Section>
    </LegalPage>
  );
}
