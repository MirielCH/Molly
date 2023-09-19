# misc.py

from decimal import Decimal, ROUND_HALF_UP

import discord

from database import codes as codes_db
from resources import emojis, settings, strings

# --- Commands ---
async def command_calculator(ctx: discord.ApplicationContext, calculation: str) -> None:
    """Calculator command"""
    def formatNumber(num):
        if num % 1 == 0:
            return int(num)
        else:
            num = num.quantize(Decimal('1.1234567890'), rounding=ROUND_HALF_UP)
            return num
    calculation = calculation.replace(' ','')
    allowedchars = set('1234567890.-+/*%()')
    if not set(calculation).issubset(allowedchars) or '**' in calculation:
        answer = (
            f'Invalid characters. Please only use numbers and supported operators.\n'
            f'Supported operators are `+`, `-`, `/`, `*` and `%`.'
        )
        if isinstance(ctx, discord.ApplicationContext):
            await ctx.respond(answer, ephemeral=True)
        else:
            await ctx.reply(answer)
        return
    error_parsing = (
        f'Error while parsing your input. Please check your input.\n'
        f'Supported operators are `+`, `-`, `/`, `*` and `%`.'
    )
    # Parse open the calculation, convert all numbers to float and store it as a list
    # This is necessary because Python has the annoying habit of allowing infinite integers which can completely lockup a system. Floats have overflow protection.
    pos = 1
    calculation_parsed = []
    number = ''
    last_char_was_operator = False # Not really accurate name, I only use it to check for *, % and /. Multiple + and - are allowed.
    last_char_was_number = False
    calculation_sliced = calculation
    try:
        while pos != len(calculation) + 1:
            slice = calculation_sliced[0:1]
            allowedcharacters = set('1234567890.-+/*%()')
            if set(slice).issubset(allowedcharacters):
                if slice.isnumeric():
                    if last_char_was_number:
                        number = f'{number}{slice}'
                    else:
                        number = slice
                        last_char_was_number = True
                    last_char_was_operator = False
                else:
                    if slice == '.':
                        if number == '':
                            number = f'0{slice}'
                            last_char_was_number = True
                        else:
                            number = f'{number}{slice}'
                    else:
                        if number != '':
                            calculation_parsed.append(Decimal(float(number)))
                            number = ''

                        if slice in ('*','%','/'):
                            if last_char_was_operator:
                                if isinstance(ctx, discord.ApplicationContext):
                                    await ctx.respond(error_parsing, ephemeral=True)
                                else:
                                    await ctx.reply(error_parsing)
                                return
                            else:
                                calculation_parsed.append(slice)
                                last_char_was_operator = True
                        else:
                            calculation_parsed.append(slice)
                            last_char_was_operator = False
                        last_char_was_number = False
            else:
                if isinstance(ctx, discord.ApplicationContext):
                    await ctx.respond(error_parsing, ephemeral=True)
                else:
                    await ctx.reply(error_parsing)
                return

            calculation_sliced = calculation_sliced[1:]
            pos += 1
        else:
            if number != '':
                calculation_parsed.append(Decimal(float(number)))
    except:
        if isinstance(ctx, discord.ApplicationContext):
            await ctx.respond(error_parsing, ephemeral=True)
        else:
            await ctx.reply(error_parsing)
        return

    # Reassemble and execute calculation
    calculation_reassembled = ''
    for slice in calculation_parsed:
        calculation_reassembled = f'{calculation_reassembled}{slice}'
    try:
        #result = eval(calculation_reassembled) # This line seems useless
        result = Decimal(eval(calculation_reassembled))
        result = formatNumber(result)
        if isinstance(result, int):
            result = f'{result:,}'
        else:
            result = f'{result:,}'.rstrip('0').rstrip('.')
        if len(result) > 2000:
            answer = 'Well. Whatever you calculated, the result is too long to display. GG.'
            if isinstance(ctx, discord.ApplicationContext):
                await ctx.respond(answer, ephemeral=True)
            else:
                await ctx.reply(answer)
            return
    except:
        answer = (
            f'Well, _that_ didn\'t calculate to anything useful.\n'
            f'What were you trying to do there? :thinking:'
        )
        if isinstance(ctx, discord.ApplicationContext):
            await ctx.respond(answer, ephemeral=True)
        else:
            await ctx.reply(answer)
        return
    if isinstance(ctx, discord.ApplicationContext):
        await ctx.respond(result)
    else:
        await ctx.reply(result)
    return


async def command_codes(ctx: discord.ApplicationContext) -> None:
    """Codes command"""
    embed = await embed_codes()
    if isinstance(ctx, discord.ApplicationContext):
        await ctx.respond(embed=embed)
    else:
        await ctx.reply(embed=embed)


# --- Embeds ---
async def embed_codes():
    """Codes"""
    field_no = 1
    codes = {field_no: ''}
    all_codes = await codes_db.get_all_codes()
    for code in sorted(all_codes):
        code_value = f'{emojis.BP} `{code.code}`{emojis.BLANK}{code.contents}'
        if len(codes[field_no]) + len(code_value) > 1020:
            field_no += 1
            codes[field_no] = ''
        codes[field_no] = f'{codes[field_no]}\n{code_value}'
    if codes[field_no] == '': codes[field_no] = f'{emojis.BP} No codes currently known'
    embed = discord.Embed(
        color = settings.EMBED_COLOR,
        title = 'Redeemable codes',
        description = (
            f'Claim these codes with {strings.SLASH_COMMANDS["code"]} to get some free goodies.\n'
            f'Every code can be redeemed once.'
        )
    )
    for field_no, field in codes.items():
        field_name = f'Codes {field_no}' if field_no > 1 else 'Codes'
        embed.add_field(name=field_name, value=field.strip(), inline=False)
    return embed