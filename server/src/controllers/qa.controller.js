// controllers/qa.controller.js
const Conversation = require("../models/Conversation");
const aiSvc        = require("../services/ai.service");
const {
  success,
  badRequest,
  notFound,
  forbidden,
  systemfailure,
} = require("../utils/response");

// ── POST /qa/query ────────────────────────────────────────────────────────────

exports.query = async (req, res) => {
  try {
    const { question, conversationId, mode = "rag", collection_filter } = req.body;

    if (!question) return badRequest(res, "question is required");

    const validModes = ["rag", "hybrid", "direct"];
    if (!validModes.includes(mode)) {
      return badRequest(res, "mode must be rag|hybrid|direct");
    }

    // Find or create conversation
    let convo;
    if (conversationId) {
      convo = await Conversation.findById(conversationId);
      if (!convo) return notFound(res, "Conversation not found");
      if (convo.userId.toString() !== req.user._id.toString()) {
        return forbidden(res, "Access denied to this conversation");
      }
    } else {
      // Auto-title from the first question (first 60 chars)
      const title = question.length > 60 ? question.slice(0, 60) + "…" : question;
      convo = await Conversation.create({ userId: req.user._id, title });
    }

    // Build conversation history for context
    const history = convo.messages.slice(-10).map((m) => ({
      role:    "user",
      content: m.userMessage,
      answer:  m.answers.at(-1)?.assistantAnswer || "",
    }));

    // Call AI service — pass convo._id as session_id for Redis session persistence
    let aiResult;
    try {
      aiResult = await aiSvc.query({
        question,
        sessionId:          convo._id.toString(),
        conversationHistory: history,
        mode,
        collection_filter,
      });
    } catch {
      return res.status(500).json({
        success: false,
        error: { code: "LLM_ERROR", message: "Failed to generate answer" },
      });
    }

    const { answer, sources = [], confidence = 0 } = aiResult;

    // Append message + answer to conversation
    const newMessage = {
      userMessage: question,
      answers: [{ assistantAnswer: answer, sources, confidence, timestamp: new Date() }],
    };
    convo.messages.push(newMessage);
    await convo.save();

    const savedMessage = convo.messages.at(-1);

    return success(res, {
      answer,
      sources,
      confidence,
      conversationId: convo._id,
      messageId:      savedMessage._id,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /qa/conversations ─────────────────────────────────────────────────────

exports.listConversations = async (req, res) => {
  try {
    const convos = await Conversation.find({ userId: req.user._id })
      .sort({ updatedAt: -1 })
      .select("title messages updatedAt");

    const out = convos.map((c) => {
      const last = c.messages.at(-1);
      return {
        _id:          c._id,
        title:        c.title,
        lastMessage:  last?.userMessage || "",
        timestamp:    c.updatedAt,
        messageCount: c.messages.length,
      };
    });

    return success(res, { conversations: out });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── GET /qa/conversations/:id ─────────────────────────────────────────────────

exports.getConversation = async (req, res) => {
  try {
    const convo = await Conversation.findById(req.params.id);
    if (!convo) return notFound(res, "Conversation not found");

    if (convo.userId.toString() !== req.user._id.toString()) {
      return forbidden(res, "Access denied to this conversation");
    }

    return success(res, {
      _id:      convo._id,
      title:    convo.title,
      messages: convo.messages,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── DELETE /qa/conversations/:id ──────────────────────────────────────────────

exports.deleteConversation = async (req, res) => {
  try {
    const convo = await Conversation.findById(req.params.id);
    if (!convo) return notFound(res, "Conversation not found");

    if (convo.userId.toString() !== req.user._id.toString()) {
      return forbidden(res, "Access denied");
    }

    await convo.deleteOne();
    return success(res, { message: "Conversation deleted successfully." });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /qa/messages/:id/feedback ───────────────────────────────────────────

exports.submitFeedback = async (req, res) => {
  try {
    const { feedback } = req.body;
    const validFeedback = ["helpful", "not_helpful"];
    if (!validFeedback.includes(feedback)) {
      return badRequest(res, "feedback must be helpful or not_helpful");
    }

    // Find the conversation that contains this message
    const convo = await Conversation.findOne({
      "messages._id": req.params.id,
      userId:          req.user._id,
    });
    if (!convo) return notFound(res, "Message not found");

    const message = convo.messages.id(req.params.id);
    const lastAnswer = message?.answers?.at(-1);
    if (!lastAnswer) return notFound(res, "Message not found");

    if (lastAnswer.feedback) {
      return res.status(409).json({
        success: false,
        error: { code: "CONFLICT", message: "Feedback already submitted for this message" },
      });
    }

    lastAnswer.feedback = feedback;
    await convo.save();

    return success(res, { message: "Feedback recorded." });
  } catch (err) {
    return systemfailure(res, err);
  }
};

// ── POST /qa/messages/:id/regenerate ─────────────────────────────────────────

exports.regenerate = async (req, res) => {
  try {
    const convo = await Conversation.findOne({
      "messages._id": req.params.id,
      userId:          req.user._id,
    });
    if (!convo) return notFound(res, "Message not found");

    const message = convo.messages.id(req.params.id);
    if (!message) return notFound(res, "Message not found");

    // Re-run AI pipeline with the same question, preserving session context
    let aiResult;
    try {
      aiResult = await aiSvc.query({
        question: message.userMessage,
        sessionId: convo._id.toString(),
        mode: "rag",
      });
    } catch {
      return res.status(500).json({
        success: false,
        error: { code: "LLM_ERROR", message: "Failed to regenerate answer" },
      });
    }

    const { answer, sources = [], confidence = 0 } = aiResult;

    // Replace the last answer (per spec: "original message is replaced")
    message.answers[message.answers.length - 1] = {
      assistantAnswer: answer,
      sources,
      confidence,
      feedback:  null,
      timestamp: new Date(),
    };

    await convo.save();

    return success(res, {
      _id:       message._id,
      role:      "assistant",
      content:   answer,
      timestamp: new Date(),
      sources,
      confidence,
      feedback:  null,
    });
  } catch (err) {
    return systemfailure(res, err);
  }
};
