import admin from "firebase-admin";
import { NextResponse } from "next/server";

const serviceAccount = JSON.parse(process.env.FIREBASE_KEY);

if (!admin.apps.length) {
  admin.initializeApp({
    credential: admin.credential.cert(serviceAccount),
  });
}

const db = admin.firestore();

export async function GET() {
  try {
    // Fetch players from Firestore
    const playersRef = db.collection("players");
    const playersSnapshot = await playersRef.get();
    if (playersSnapshot.empty) {
      console.error("No players found in Firestore.");
      return new Response(JSON.stringify({ error: "No players found" }), {
        status: 404,
      });
    }

    let players = playersSnapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
    console.log("Players:", players);

    // Fetch prop_lines from Firestore
    const propLinesRef = db.collection("prop_lines");
    const propLinesSnapshot = await propLinesRef.get();
    if (propLinesSnapshot.empty) {
      console.error("No prop_lines found in Firestore.");
      return new Response(JSON.stringify({ error: "No prop_lines found" }), {
        status: 404,
      });
    }

    let propLinesData = {};
    propLinesSnapshot.docs.forEach((doc) => {
      propLinesData[doc.id] = doc.data();
    });
    console.log("Prop Lines Data:", propLinesData);

    // Merge player data with prop_lines data
    players = players.map((player) => {
      const propLineData = propLinesData[player.id] || {};
      return {
        ...player,
        prop_line: propLineData.prop_line || 0,
        projection: propLineData.projection_data || {},
      };
    });

    return NextResponse.json(players);
  } catch (error) {
    console.error("Error fetching players:", error);
    return new Response(
      JSON.stringify({ error: "Failed to fetch players", details: error.message }),
      { status: 500 }
    );
  }
}