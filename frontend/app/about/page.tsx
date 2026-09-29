import type { Metadata } from "next";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "About" };

export default function About() {
  return (
    <div className="prose">
      <h1>About {site.name}</h1>
      <p>
        {site.name} makes calm, well-made organisation pieces for people making the most of small UK homes:
        flats, house shares and home offices.
      </p>
      <p>
        We name our materials exactly, publish measured dimensions, photograph the real product, dispatch from
        the UK and keep returns simple.
      </p>
      <h2>Who we are</h2>
      <p><span className="todo">{site.legalName}</span>, <span className="todo">{site.address}</span></p>
      <p>Contact: <a href={`mailto:${site.email}`}>{site.email}</a></p>
    </div>
  );
}
