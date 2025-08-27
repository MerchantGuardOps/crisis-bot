// MerchantGuard Complete Bot
const { Telegraf, Markup } = require('telegraf');

const BOT_TOKEN = process.env.BOT_TOKEN;

const GUIDES = {
  section43: {
    title: 'Section 4.3 Stripe Fund Release Guide',
    summary: '87% fund recovery; 30–60 day acceleration vs 94-day generic waiting.',
    checklist: [
      '• Confirm payment account and acquirer reference number',
      '• Assemble cause-cured evidence (dated fixes, security improvements, logs)', 
      '• Draft Section 4.3 compliance letter with before/after metrics',
      '• Submit via acquirer portal; request written SLA; track weekly status'
    ]
  },
  match: {
    title: 'MATCH Removal — 10-Day Filing Strategy',
    summary: '94% success rate with 10-day filing vs "wait 5 years" generic advice.',
    checklist: [
      '• Confirm exact reason code and placing acquirer identity',
      '• Build comprehensive cause-cured evidence with dated proof documents',
      '• Draft one-page removal letter (timeline, fixes, quantified metrics)', 
      '• Submit via acquirer and track response; escalate at day 21 if needed'
    ]
  },
  highrisk: {
    title: 'Emergency High-Risk Setup (48–72h)',
    summary: '48–72 hour emergency processing vs 5–14 day generic timelines.',
    checklist: [
      '• Pick emergency descriptor strategy and geo/BIN routing rules',
      '• Enable 3DS on high-risk traffic only; TRA exemptions on clean transactions',
      '• Stand up bridge processor; freeze risky traffic patterns for 72h',
      '• Set up emergency alerts + refund protocols; publish crisis support line'
    ]
  }
};

function parsePayload(input) {
  if (!input) return {};
  const out = {};
  
  for (const part of String(input).split(';')) {
    const [key, value] = part.split(':');
    if (key && value) {
      out[key.trim()] = value.trim();
    }
  }
  return out;
}

const bot = new Telegraf(BOT_TOKEN);

// Main Welcome with Hero Image
bot.start(async (ctx) => {
  console.log('✅ MerchantGuard start from:', ctx.from.username || ctx.from.first_name);
  
  const payload = parsePayload(ctx.startPayload);
  
  // Crisis Fast-Track Flow
  if (payload.g && GUIDES[payload.g]) {
    const guide = GUIDES[payload.g];
    
    try {
      await ctx.replyWithPhoto(
        'https://www.merchantguard.ai/Hero-image-merchantguard-v2.jpg',
        {
          caption: `🚨 **Payment Emergency Detected**\n\n` +
                  `**${guide.title}**\n\n` +
                  `${guide.summary}\n\n` +
                  `Here's your immediate 2-minute action checklist:`,
          parse_mode: 'Markdown'
        }
      );
    } catch (error) {
      await ctx.reply(`🚨 **Payment Emergency Detected**\n\n**${guide.title}**\n\n${guide.summary}`, 
        { parse_mode: 'Markdown' });
    }
    
    for (const step of guide.checklist) {
      await ctx.reply(step);
    }
    
    await ctx.reply(
      '**Ready to resolve this crisis?**\n\n' +
      '✅ Professional legal templates\n' +
      '✅ Step-by-step implementation guide\n' +
      '✅ Direct emergency processing contacts\n' +
      '✅ 48-72h emergency setup\n\n' +
      '**Emergency Pack — $199**',
      Markup.inlineKeyboard([
        [Markup.button.callback('💳 Buy Emergency Pack — $199', 'buy_emergency_199')],
        [Markup.button.callback('🎯 Get Full Assessment', 'start_guardscore')]
      ]), { parse_mode: 'Markdown' }
    );
    
    return;
  }
  
  // Main Welcome with Hero Image
  try {
    await ctx.replyWithPhoto(
      'https://www.merchantguard.ai/Hero-image-merchantguard-v2.jpg',
      {
        caption: '🛡️ **Welcome to MerchantGuard**\n\n' +
                'We help founders issue a Compliance Passport so they can switch payment providers without starting over.\n\n' +
                'Before we begin, please review and accept our Terms of Service and Privacy Policy.\n\n' +
                '🔒 **What We Protect:**\n' +
                '• Your data is encrypted and never shared without consent\n' +
                '• Assessments are confidential and anonymized\n' +
                '• You control who sees your GuardScore™ results\n\n' +
                '⚖️ **Legal Framework:**\n' +
                '• GuardScore™ is for informational purposes only\n' +
                '• Not financial, legal, or investment advice\n' +
                '• Results help demonstrate compliance readiness\n\n' +
                '📊 **Data Collection:**\n' +
                '• Business profile and compliance metrics\n' +
                '• Used solely for passport generation\n' +
                '• Stored with enterprise-grade security\n\n' +
                'By continuing, you agree to our complete Terms of Service and Privacy Policy.',
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          [Markup.button.callback('✅ Accept & Continue', 'accept_terms')],
          [Markup.button.url('📋 Read Terms', 'https://merchantguard.ai/terms')],
          [Markup.button.url('🔒 Privacy Policy', 'https://merchantguard.ai/privacy')]
        ])
      }
    );
  } catch (error) {
    console.log('❌ Hero image failed:', error.message);
    await ctx.reply(
      '🛡️ **Welcome to MerchantGuard**\n\n' +
      'We help founders issue a Compliance Passport so they can switch payment providers without starting over.\n\n' +
      'Before we begin, please review and accept our Terms of Service and Privacy Policy.\n\n' +
      '🔒 **What We Protect:**\n' +
      '• Your data is encrypted and never shared without consent\n' +
      '• Assessments are confidential and anonymized\n' +
      '• You control who sees your GuardScore™ results\n\n' +
      '⚖️ **Legal Framework:**\n' +
      '• GuardScore™ is for informational purposes only\n' +
      '• Not financial, legal, or investment advice\n' +
      '• Results help demonstrate compliance readiness\n\n' +
      '📊 **Data Collection:**\n' +
      '• Business profile and compliance metrics\n' +
      '• Used solely for passport generation\n' +
      '• Stored with enterprise-grade security\n\n' +
      'By continuing, you agree to our complete Terms of Service and Privacy Policy.',
      {
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          [Markup.button.callback('✅ Accept & Continue', 'accept_terms')],
          [Markup.button.url('📋 Read Terms', 'https://merchantguard.ai/terms')],
          [Markup.button.url('🔒 Privacy Policy', 'https://merchantguard.ai/privacy')]
        ])
      }
    );
  }
});

// Handle terms acceptance
bot.action('accept_terms', async (ctx) => {
  await ctx.answerCbQuery();
  
  await ctx.reply(
    '**Choose Your Assessment Path:**\n\n' +
    '🚀 **Fast Track (3 min)** - Quick score + instant templates ($199)\n' +
    '🔍 **Full Assessment (10 min)** - Complete analysis + HMAC passport\n' +
    '💎 **Premium Kit** - Custom strategy + expert review ($499)\n\n' +
    '⚠️ **Legal Requirement:**\n' +
    'Before proceeding, you must accept our Terms of Service. Our assessment is for educational purposes only and does not constitute financial, legal, or investment advice.\n\n' +
    '🔒 **Your Data Protection:**\n' +
    '• All responses are cryptographically signed\n' +
    '• Passports are tamper-evident with HMAC verification\n' +
    '• Enterprise-grade security and compliance\n\n' +
    'Ready to get your GuardScore™?',
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        [Markup.button.callback('✅ I Accept Terms of Service', 'start_assessment')],
        [Markup.button.callback('🚀 Fast Track ($199)', 'fast_track_199')],
        [Markup.button.url('📋 Read Full Terms', 'https://merchantguard.ai/terms')]
      ])
    }
  );
});

// Handle all other actions
bot.action('start_assessment', async (ctx) => {
  await ctx.answerCbQuery();
  await ctx.reply(
    '🎯 **Starting Full Assessment**\n\n' +
    'This will take about 10 minutes and cover:\n' +
    '• Payment processing setup\n' +
    '• Risk mitigation strategies\n' +
    '• Compliance requirements\n' +
    '• Emergency preparedness\n\n' +
    'Let\'s begin with your business profile...',
    { parse_mode: 'Markdown' }
  );
});

bot.action('fast_track_199', async (ctx) => {
  await ctx.answerCbQuery();
  await ctx.reply(
    '🚀 **Fast Track Assessment**\n\n' +
    'Get instant results + professional templates\n\n' +
    '✅ 3-minute quick assessment\n' +
    '✅ Instant GuardScore\n' +
    '✅ Professional templates\n' +
    '✅ Emergency Pack included\n\n' +
    '**Fast Track - $199**',
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        [Markup.button.url('Buy Fast Track', 'https://merchantguard.ai/packages-simple')]
      ])
    }
  );
});

bot.action('buy_emergency_199', async (ctx) => {
  await ctx.answerCbQuery();
  await ctx.reply(
    '💳 **Emergency Pack Purchase**\n\n' +
    'Redirecting to secure payment...\n\n' +
    'After purchase, you\'ll receive:\n' +
    '• Professional legal templates\n' +
    '• Emergency contact directory\n' +
    '• Step-by-step recovery guide\n' +
    '• 72h priority support',
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        [Markup.button.url('Complete Purchase', 'https://merchantguard.ai/packages-simple')]
      ])
    }
  );
});

bot.action('start_guardscore', async (ctx) => {
  await ctx.answerCbQuery();
  await ctx.reply(
    '🎯 **Full Assessment**\n\n' +
    'Get your complete risk profile and customized recommendations.\n\n' +
    'Takes 10 minutes, covers:\n' +
    '• Payment processing setup\n' +
    '• Risk mitigation strategies\n' +
    '• Compliance requirements\n' +
    '• Emergency preparedness',
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        [Markup.button.url('Start Assessment', 'https://merchantguard.ai/tools/guardscore-telegram')]
      ])
    }
  );
});

// Vercel serverless function export
module.exports = async (req, res) => {
  try {
    if (req.method === 'POST') {
      await bot.handleUpdate(req.body);
      res.status(200).json({ ok: true });
    } else {
      res.status(200).json({ message: 'MerchantGuard Bot Ready!', timestamp: new Date().toISOString() });
    }
  } catch (error) {
    console.error('Bot error:', error);
    res.status(500).json({ error: 'Bot error' });
  }
};

// For local testing
if (require.main === module) {
  bot.launch();
  console.log('🚀 MerchantGuard Bot STARTED!');
  process.once('SIGINT', () => bot.stop('SIGINT'));
  process.once('SIGTERM', () => bot.stop('SIGTERM'));
}