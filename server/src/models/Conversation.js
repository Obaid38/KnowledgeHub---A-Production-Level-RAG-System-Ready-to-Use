// models/Conversation.js
// Each message holds the user question and an array of AI answers
// (the array supports answer regeneration without losing history).
const mongoose = require("mongoose");

const sourceSchema = new mongoose.Schema(
  {
    _id:      { type: mongoose.Schema.Types.ObjectId, ref: "Document" },
    filename: String,
    type:     String,
    page:     Number,
  },
  { _id: false }
);

const answerSchema = new mongoose.Schema(
  {
    assistantAnswer: { type: String, required: true },
    sources:         { type: [sourceSchema], default: [] },
    confidence:      { type: Number, default: 0 },
    feedback:        { type: String, enum: ["helpful", "not_helpful", null], default: null },
    timestamp:       { type: Date, default: Date.now },
  },
  { _id: false }
);

const messageSchema = new mongoose.Schema(
  {
    userMessage: { type: String, required: true },
    answers:     { type: [answerSchema], default: [] },
  },
  { timestamps: true }
);

const conversationSchema = new mongoose.Schema(
  {
    userId:       { type: mongoose.Schema.Types.ObjectId, ref: "User", required: true, index: true },
    title:        { type: String, default: "New Conversation" },
    messages:     { type: [messageSchema], default: [] },
  },
  { timestamps: true }
);

module.exports = mongoose.model("Conversation", conversationSchema);
