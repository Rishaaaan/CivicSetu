// functions/index.js (CommonJS)
const { onDocumentCreated, onDocumentUpdated, onDocumentWritten } = require("firebase-functions/v2/firestore");
const { setGlobalOptions } = require("firebase-functions/v2");
const functions = require("firebase-functions");
const admin = require("firebase-admin");

// Initialize Firebase Admin if not already initialized
if (!admin.apps.length) {
  admin.initializeApp();
}

// Set global options
setGlobalOptions({ maxInstances: 10 });

// Initialize Firestore
const db = admin.firestore();

// // fetch: use global fetch if available (Cloud Functions Node18), otherwise try node-fetch
// let fetchFn = globalThis.fetch;
// if (!fetchFn) {
//   try {
//     fetchFn = require("node-fetch");
//   } catch (e) {
//     throw new Error("fetch not available and node-fetch is not installed.");
//   }
// }
// const fetch = fetchFn;

// if (!admin.apps.length) admin.initializeApp();
// const db = admin.firestore();
// setGlobalOptions({ maxInstances: 10 });

// // HF token: try environment var first, then firebase functions config fallback
// const HF_TOKEN = process.env.HF_TOKEN || (functions.config && functions.config().hf && functions.config().hf.token) || "";

// // ---------- Helpers ----------
// function extractCaptionFromPredictResponse(json) {
//   // Gradio /api/predict tends to return { data: [prompt, caption] }
//   if (!json) return null;
//   if (typeof json === "string") return json;
//   if (Array.isArray(json)) {
//     return json[1] || json[0] || null;
//   }
//   if (json.data && Array.isArray(json.data)) {
//     return json.data[1] || json.data[0] || null;
//   }
//   // fallback to any textual field
//   if (json.caption) return json.caption;
//   return null;
// }

// function normalizePriorityResponse(resp) {
//   // resp could be string, array, object - return a readable string
//   if (typeof resp === "string") return resp;
//   if (Array.isArray(resp)) return resp[0] !== undefined ? String(resp[0]) : JSON.stringify(resp);
//   if (resp && typeof resp === "object") {
//     if (resp.priority) return String(resp.priority);
//     if (resp.data && Array.isArray(resp.data)) return String(resp.data[0] ?? JSON.stringify(resp.data));
//     // If it's a one-field object with a string value, return that
//     const keys = Object.keys(resp);
//     if (keys.length === 1 && typeof resp[keys[0]] === "string") return resp[keys[0]];
//     return JSON.stringify(resp);
//   }
//   return String(resp);
// }

// async function fetchImageDataUrl(imageUrl) {
//   const res = await fetch(imageUrl);
//   if (!res.ok) throw new Error(`Failed to fetch image: ${res.status} ${res.statusText}`);
//   const contentType = res.headers && (res.headers.get ? res.headers.get("content-type") : res.headers["content-type"]) || "image/jpeg";
//   const arrayBuffer = await res.arrayBuffer();
//   const b64 = Buffer.from(arrayBuffer).toString("base64");
//   return `data:${contentType};base64,${b64}`;
// }

// // Try posting to a HF Space via its /api/predict/ endpoint
// async function trySpacePredict(spaceName, imageDataUrl, opts = {}) {
//   // opts may include args array custom for the space
//   const spaceUrl = spaceName.replace("/", "-"); // fancyfeast/joy-caption-alpha-two -> fancyfeast-joy-caption-alpha-two
//   const url = `https://${spaceUrl}.hf.space/api/predict/`;
//   // default arguments for Joy caption spaces: [image, caption_type, caption_length, extra_options, name_input, custom_prompt]
//   const args = opts.args || [imageDataUrl, "Descriptive", "any", [], "User", "Generate a useful caption for this image."];

//   // attempt 1: no auth
//   let res = await fetch(url, {
//     method: "POST",
//     headers: { "Content-Type": "application/json" },
//     body: JSON.stringify({ data: args }),
//   });

//   // if auth is available and we got an error, try with auth
//   if ((!res.ok || res.status >= 400) && HF_TOKEN) {
//     res = await fetch(url, {
//       method: "POST",
//       headers: { "Content-Type": "application/json", "Authorization": `Bearer ${HF_TOKEN}` },
//       body: JSON.stringify({ data: args }),
//     });
//   }

//   if (!res.ok) {
//     const txt = await res.text().catch(() => "");
//     const err = new Error(`Space ${spaceName} returned ${res.status}: ${txt}`);
//     err.status = res.status;
//     throw err;
//   }

//   const json = await res.json();
//   const caption = extractCaptionFromPredictResponse(json);
//   if (!caption) throw new Error(`Space ${spaceName} returned no caption`);
//   return caption;
// }

// // Try HF inference model (byte-stream upload)
// async function tryInferenceModel(modelId, arrayBuffer) {
//   if (!HF_TOKEN) throw new Error("HF token required for inference API fallback");
//   const url = `https://api-inference.huggingface.co/models/${modelId}`;
//   const res = await fetch(url, {
//     method: "POST",
//     headers: {
//       Authorization: `Bearer ${HF_TOKEN}`,
//       "Content-Type": "application/octet-stream",
//     },
//     body: Buffer.from(arrayBuffer),
//   });

//   if (!res.ok) {
//     const txt = await res.text().catch(() => "");
//     throw new Error(`Inference ${modelId} returned ${res.status}: ${txt}`);
//   }

//   const json = await res.json();
//   // many inference models return [{ generated_text: "..." }] or { generated_text: "..." }
//   if (Array.isArray(json) && json[0] && json[0].generated_text) return json[0].generated_text;
//   if (json.generated_text) return json.generated_text;
//   // vit-gpt2 returns [{generated_text: "..."}] often
//   if (json[0] && json[0].generated_text) return json[0].generated_text;
//   // try other heuristics
//   if (Array.isArray(json)) return String(json[0]);
//   throw new Error("Inference returned unexpected shape");
// }

// // try multiple caption sources in order
// async function generateCaptionFromImageUrl(imageUrl) {
//   // fetch image data url and raw bytes
//   const res = await fetch(imageUrl);
//   if (!res.ok) throw new Error(`Failed to fetch image: ${res.status}`);
//   const contentType = res.headers && (res.headers.get ? res.headers.get("content-type") : res.headers["content-type"]) || "image/jpeg";
//   const arrayBuffer = await res.arrayBuffer();
//   const imageDataUrl = `data:${contentType};base64,${Buffer.from(arrayBuffer).toString("base64")}`;

//   const attempts = [
//     async () => await trySpacePredict("fancyfeast/joy-caption-alpha-two", imageDataUrl, { args: [imageDataUrl, "Descriptive", "any", [], "User", "Generate a useful caption for this image."] }),
//     async () => await trySpacePredict("fancyfeast/joy-caption-beta-one", imageDataUrl, { args: [imageDataUrl, "Descriptive", "long", [], "User", "Generate a useful caption for this image."] }),
//     async () => await tryInferenceModel("nlpconnect/vit-gpt2-image-captioning", arrayBuffer),
//   ];

//   for (const fn of attempts) {
//     try {
//       const caption = await fn();
//       if (caption && caption.length > 6) return caption;
//     } catch (err) {
//       console.warn("caption source failed:", err.message || err);
//       // if server-side transient (429/503), try one more time quickly
//       if (err.status && [429, 502, 503, 504].includes(err.status)) {
//         await new Promise(r => setTimeout(r, 800));
//         try {
//           const caption = await fn();
//           if (caption && caption.length > 6) return caption;
//         } catch (e2) {
//           console.warn("retry failed:", e2.message || e2);
//         }
//       }
//       continue;
//     }
//   }

//   // final fallback
//   return "Image content";
// }

// // ---------- Cloud Functions ----------

// exports.generateCaptionOnReportCreate = onDocumentCreated("reports/{reportId}", async (event) => {
//   const report = event.data.data();
//   const reportId = event.params.reportId;
//   if (!report || !report.image_url) {
//     console.log(`No image_url for ${reportId}`);
//     return null;
//   }

//   try {
//     console.log(`Processing report ${reportId} image ${report.image_url}`);
//     const caption = await generateCaptionFromImageUrl(report.image_url);
//     console.log("Caption generated:", caption);
//     await db.collection("reports").doc(reportId).update({ image_caption: caption });
//     console.log("Firestore updated with caption for", reportId);
//   } catch (err) {
//     console.error("Error generating caption:", err);
//     try {
//       await db.collection("reports").doc(reportId).update({ image_caption: "Image content" });
//       console.log("Firestore updated with fallback caption for", reportId);
//     } catch (uerr) {
//       console.error("Failed fallback update:", uerr);
//     }
//   }

//   return null;
// });

// HF token: try environment var first, then firebase functions config fallback
const HF_TOKEN = process.env.HF_TOKEN || "";

// Helper function to send email notification
async function sendEmailNotification(userEmail, username, reportTitle, reportId, isRejected = false) {
  try {
    if (!EMAIL_API_KEY) {
      console.log("Email API key not configured, skipping email notification");
      return;
    }

    const subject = isRejected ? "Report Rejected - CivicConnect" : "Report Status Update - CivicConnect";
    const status = isRejected ? "rejected" : "updated";
    const statusColor = isRejected ? "#e74c3c" : "#3498db";
    
    const emailBody = `
      <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px;">
          <h2 style="color: #2c3e50; margin-bottom: 20px;">Report Status Update</h2>
          
          <div style="background-color: white; padding: 20px; border-radius: 8px; border-left: 4px solid ${statusColor};">
            <p>Dear ${username},</p>
            
            <p>Your report "<strong>${reportTitle}</strong>" has been <strong style="color: ${statusColor};">${status}</strong> by our admin team.</p>
            
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin: 15px 0;">
              <p><strong>Report ID:</strong> ${reportId}</p>
              <p><strong>Report Title:</strong> ${reportTitle}</p>
              <p><strong>Status:</strong> <span style="color: ${statusColor}; font-weight: bold;">${status.toUpperCase()}</span></p>
            </div>
            
            ${isRejected ? `
              <p style="color: #e74c3c; font-weight: bold;">
                Your report has been rejected. This could be due to insufficient information, 
                inappropriate content, or the issue not falling under municipal jurisdiction.
              </p>
              <p>You can submit a new report with more detailed information if needed.</p>
            ` : `
              <p style="color: #27ae60;">
                Thank you for using CivicConnect to report civic issues. We appreciate your contribution 
                to making our city better.
              </p>
            `}
            
            <p>Best regards,<br>
            The CivicConnect Team</p>
          </div>
        </div>
      </div>
    `;

    // Using a generic email service (you can replace with SendGrid, Nodemailer, etc.)
    const emailPayload = {
      to: userEmail,
      from: SENDER_EMAIL,
      subject: subject,
      html: emailBody
    };

    // Example with fetch to a generic email API (replace with your preferred service)
    const response = await fetch("YOUR_EMAIL_SERVICE_ENDPOINT", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${EMAIL_API_KEY}`
      },
      body: JSON.stringify(emailPayload)
    });

    if (response.ok) {
      console.log(`Email sent successfully to ${userEmail}`);
    } else {
      console.error(`Failed to send email: ${response.status} ${response.statusText}`);
    }
  } catch (error) {
    console.error("Error sending email notification:", error);
  }
}
// Helper function to normalize priority response
function normalizePriorityResponse(resp) {
  // resp could be string, array, object - return a readable string
  if (typeof resp === "string") return resp;
  if (Array.isArray(resp)) return resp[0] !== undefined ? String(resp[0]) : JSON.stringify(resp);
  if (resp && typeof resp === "object") {
    if (resp.priority) return String(resp.priority);
    if (resp.data && Array.isArray(resp.data)) return String(resp.data[0] ?? JSON.stringify(resp.data));
    // If it's a one-field object with a string value, return that
    const keys = Object.keys(resp);
    if (keys.length === 1 && typeof resp[keys[0]] === "string") return resp[keys[0]];
    return JSON.stringify(resp);
  }
  return String(resp);
}

// New function to handle report status changes and send notifications
exports.notifyOnReportStatusChange = onDocumentUpdated("reports/{reportId}", async (event) => {
  try {
    const beforeData = event.data.before?.data() || {};
    const afterData = event.data.after?.data();
    const reportId = event.params.reportId;

    console.log(`Checking report ${reportId} for status changes`);

    if (!afterData) {
      console.log("No after data, skipping notification");
      return null;
    }

    // Check if the report was just rejected (rejected field changed from false/undefined to true)
    const wasRejected = !beforeData.rejected && afterData.rejected === true;
    
    // Check if status changed (you can also monitor other status changes)
    const statusChanged = beforeData.status !== afterData.status;

    if (!wasRejected && !statusChanged) {
      console.log("No relevant status changes, skipping notification");
      return null;
    }

    const userId = afterData.user_id;
    if (!userId) {
      console.log("No user_id found in report, skipping notification");
      return null;
    }

    // Get user data to retrieve FCM token and email
    const userDoc = await db.collection("users").doc(userId).get();
    
    if (!userDoc.exists) {
      console.log(`User document not found for userId: ${userId}`);
      return null;
    }

    const userData = userDoc.data();
    const fcmToken = userData.fcmToken;
    const username = userData.name || userData.username || "User";

    console.log(`Found user data for ${username}`);

    // Send FCM notification if token exists
    if (fcmToken) {
      try {
        let title = "Report Update";
        let body = "";
        
        if (wasRejected) {
          title = "Report Rejected";
          body = `Your report "${afterData.title}" has been rejected by the admin team.`;
        } else if (statusChanged) {
          title = "Report Status Changed";
          body = `Your report "${afterData.title}" status changed to: ${afterData.status}`;
        }

        const message = {
          notification: {
            title: title,
            body: body,
            //icon: "ic_notification" // Make sure you have this icon in your Android app
          },
          data: {
            reportId: reportId,
            reportTitle: afterData.title || "",
            status: afterData.status || "",
            rejected: afterData.rejected ? "true" : "false",
            type: "report_update"
          },
          token: fcmToken,
          android: {
            notification: {
              channelId: "reports_channel",
              priority: "high",
              defaultSound: true
            }
          }
        };

        const response = await admin.messaging().send(message);
        console.log(`FCM notification sent successfully: ${response}`);
        
      } catch (fcmError) {
        console.error("Error sending FCM notification:", fcmError);
        
        // If token is invalid, remove it from user document
        if (fcmError.code === 'messaging/registration-token-not-registered') {
          await db.collection("users").doc(userId).update({
            fcmToken: admin.firestore.FieldValue.delete()
          });
          console.log("Removed invalid FCM token from user document");
        }
      }
    } else {
      console.log("No FCM token found for user");
    }

    return null;
  } catch (error) {
    console.error("Error in notifyOnReportStatusChange:", error);
    return null;
  }
});

exports.setPriorityOnImageCaption = onDocumentUpdated("reports/{reportId}", async (event) => {
  try {
    const beforeData = event.data.before?.data() || {};
    const afterData = event.data.after?.data();
    const reportId = event.params.reportId;

    console.log(`Processing report ${reportId} for priority update`);

    if (!afterData) {
      console.log("No after data, skipping");
      return null;
    }

    // run only when caption changed or priority missing
    if ((beforeData.image_caption === afterData.image_caption) && afterData.priority) {
      console.log("Caption unchanged and priority exists, skipping");
      return null;
    }
    
    const textToSend = `${afterData.image_caption || ""} ${afterData.user_description || ""}`.trim();
    console.log("Sending to Priority API:", textToSend);

    if (!textToSend) {
      console.log("No text to analyze, setting default priority");
      await db.collection("reports").doc(reportId).update({ priority: "medium" });
      return null;
    }

    const priorityApiUrl = "https://omeeshahah-civic-priority-api.hf.space/predict";
    const headers = { "Content-Type": "application/json" };
    if (HF_TOKEN) headers["Authorization"] = `Bearer ${HF_TOKEN}`;

    const response = await fetch(priorityApiUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({ text: textToSend })
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => "");
      console.warn(`Priority API returned ${response.status}: ${errorText}`);
      // fallback priority
      await db.collection("reports").doc(reportId).update({ priority: "medium" });
      return null;
    }

    const json = await response.json();
    const priority = normalizePriorityResponse(json);
    console.log("Normalized priority:", priority);

    await db.collection("reports").doc(reportId).update({ priority });
    console.log("Updated report priority:", reportId, priority);
    
    return null;
  } catch (err) {
    console.error("Error in setPriorityOnImageCaption:", err);
    try {
      await db.collection("reports").doc(event.params.reportId).update({ priority: "medium" });
      console.log("Applied fallback priority due to error");
    } catch (updateErr) {
      console.error("Failed to apply fallback priority:", updateErr);
    }
    return null;
  }
});

// Mapping of old departments to new ones
const departmentMap = {
  "Road Maintenance": "Roads and Bridges PWD",
  "Street Lighting": "Street Lighting / Electrical Department",
  "Water Supply": "Water Supply & Sewerage Department",
  "Garbage Collection": "Solid Waste Management (SWM)", // highlight in frontend with blue
  "Public Transport": "Public Health & Sanitation",
  "Noise Complaint": "Noise & Pollution Control Cell"
};

exports.normalizeDepartment = onDocumentWritten("reports/{reportId}", async (event) => {
  try {
    const afterData = event.data?.after?.data();
    const beforeData = event.data?.before?.data();
    const reportId = event.params.reportId;

    console.log(`Processing department normalization for report ${reportId}`);

    if (!afterData) {
      console.log("Document deleted, skipping");
      return null; // document deleted
    }

    const currentDept = afterData.department;

    // Only update if department exists in the mapping and hasn't already been normalized
    if (departmentMap[currentDept] && beforeData?.department !== departmentMap[currentDept]) {
      const newDept = departmentMap[currentDept];
      console.log(`Updating department for report ${reportId}: ${currentDept} → ${newDept}`);

      await db.collection("reports").doc(reportId).update({
        department: newDept
      });
      console.log(`Successfully updated department for report ${reportId}`);
    } else {
      console.log("No department update needed");
    }

    return null;
  } catch (err) {
    console.error("Error in normalizeDepartment:", err);
    return null;
  }
});