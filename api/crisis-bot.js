// MerchantGuard Crisis Fast-Track Bot API Endpoint
const { Telegraf, Markup } = require('telegraf');

const BOT_TOKEN = process.env.BOT_TOKEN || '7928143141:AAGHheF2fyq_dHcVmz-VdqlS9H26Fs3maEo';

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

// Crisis Fast-Track with hero image
bot.start(async (ctx) => {
  console.log('✅ Crisis bot start from:', ctx.from.username || ctx.from.first_name);
  
  const payload = parsePayload(ctx.startPayload);
  
  // Crisis Fast-Track Flow - bypass GuardScore
  if (payload.g && GUIDES[payload.g]) {
    const guide = GUIDES[payload.g];
    
    // Send hero with crisis message
    try {
      await ctx.replyWithPhoto(
        'https://merchantguard.ai/Hero-image-merchantguard.jpg',
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
    
    // Send checklist
    for (const step of guide.checklist) {
      await ctx.reply(step);
    }
    
    // Send next steps with Emergency Pack
    await ctx.reply(
      '**Next Step:**',
      Markup.inlineKeyboard([
        [Markup.button.url('▶ Start Emergency Pack — $199', 'https://t.me/guardscorebot?start=pkg_auto_199')],
        [Markup.button.url('🎯 Get GuardScore (60s)', 'https://t.me/guardscorebot?start=guardscore')]
      ]), { parse_mode: 'Markdown' }
    );
    
    return;
  }
  
  // Default menu with hero image
  try {
    await ctx.replyWithPhoto(
      'https://merchantguard.ai/Hero-image-merchantguard.jpg',
      {
        caption: '🚨 **MerchantGuard Crisis Fast-Track**\n\n' +
                'Payment emergency? Get immediate professional help.\n\n' +
                '**Crisis Bypass:** No assessment required\n' +
                '**Professional Templates:** Legal-grade documents\n' +
                '**Direct Solutions:** Emergency processing in 48-72h\n\n' +
                'Choose your crisis:',
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          [Markup.button.callback('🚑 Section 4.3 Fund Release', 'guide_section43')],
          [Markup.button.callback('⚡ Emergency High-Risk Setup', 'guide_highrisk')], 
          [Markup.button.callback('🧹 MATCH Removal Filing', 'guide_match')],
          [Markup.button.url('🎯 Get Full GuardScore', 'https://t.me/guardscorebot?start=guardscore')]
        ])
      }
    );
  } catch (error) {
    console.log('Hero image failed, sending text menu');
    await ctx.reply(
      '🚨 **MerchantGuard Crisis Fast-Track**\n\n' +
      'Payment emergency? Get immediate professional help.\n\n' +
      '**Crisis Bypass:** No assessment required\n' +
      '**Professional Templates:** Legal-grade documents\n' +
      '**Direct Solutions:** Emergency processing in 48-72h',
      { parse_mode: 'Markdown' }
    );
  }
});

// Handle inline button callbacks - deliver content directly
bot.action(/guide_(.+)/, async (ctx) => {
  const guideType = ctx.match[1];
  const guide = GUIDES[guideType];
  
  await ctx.answerCbQuery();
  
  if (!guide) return;
  
  // Send hero with crisis message
  try {
    await ctx.replyWithPhoto(
      'https://merchantguard.ai/Hero-image-merchantguard.jpg',
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
  
  // Send checklist
  for (const step of guide.checklist) {
    await ctx.reply(step);
  }
  
  // Send Emergency Pack offer
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
});

// Handle purchase buttons
bot.action('buy_emergency_199', async (ctx) => {
  await ctx.answerCbQuery();
  
  // This would connect to your Stripe/payment system
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
    'Takes 60 seconds, covers:\n' +
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

// Vercel API endpoint
module.exports = async (req, res) => {
  try {
    if (req.method === 'POST') {
      await bot.handleUpdate(req.body);
      res.status(200).json({ ok: true });
    } else {
      res.status(200).json({ message: 'Crisis Fast-Track Bot API Ready!', timestamp: new Date().toISOString() });
    }
  } catch (error) {
    console.error('Crisis bot error:', error);
    res.status(500).json({ error: 'Crisis bot error' });
  }
};